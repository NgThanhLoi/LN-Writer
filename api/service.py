"""
AsyncNovelService — wraps the synchronous pipeline in a thread,
coordinates checkpoints via asyncio.Event, and broadcasts
progress via WebSocket to all connected clients.
"""
import asyncio
import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)
from dataclasses import asdict
from typing import Callable

from core.ai_adapter import init_gemini, build_adapter
from core.agents.plot_navigator import PlotNavigatorAgent
from core.agents.character_soul import CharacterSoulAgent
from core.agents.draft_master import DraftMasterAgent
from core.agents.final_auditor import FinalAuditorAgent
from core.models import Chapter, CharacterProfile, CharacterRelationship, NovelProject, NovelStatus, StoryBlueprint
from core.prompts.writer_prompts import CHAPTER_SUMMARY_PROMPT
from config import GEMINI_API_KEY
import api.database as db

MAX_REGEN_PER_CHAPTER = 3
_executor = ThreadPoolExecutor(max_workers=4)


# ── Broadcaster ────────────────────────────────────────────────────────────

class Broadcaster:
    """Fan-out: one novel → many WebSocket connections."""

    def __init__(self):
        # novel_id → set of async queues
        self._queues: dict[str, set[asyncio.Queue]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        # novel_id → monotonically increasing sequence number
        self._seq: dict[str, int] = {}

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self, novel_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues.setdefault(novel_id, set()).add(q)
        return q

    def unsubscribe(self, novel_id: str, q: asyncio.Queue) -> None:
        if novel_id in self._queues:
            self._queues[novel_id].discard(q)

    def publish(self, novel_id: str, event: dict) -> None:
        """Called from background thread — thread-safe via call_soon_threadsafe."""
        loop = self._loop
        if loop is None or not loop.is_running():
            return
        seq = self._seq.get(novel_id, 0) + 1
        self._seq[novel_id] = seq
        event = {**event, "seq": seq}
        for q in list(self._queues.get(novel_id, [])):
            loop.call_soon_threadsafe(q.put_nowait, event)


broadcaster = Broadcaster()


# ── Checkpoint gates ───────────────────────────────────────────────────────

class CheckpointGate:
    """Pause pipeline until frontend sends approval."""

    def __init__(self):
        self._events: dict[str, asyncio.Event] = {}
        self._decisions: dict[str, str] = {}
        self._data: dict[str, any] = {}

    def create(self, key: str) -> asyncio.Event:
        ev = asyncio.Event()
        self._events[key] = ev
        return ev

    def resolve(self, key: str, decision: str, data=None) -> None:
        self._decisions[key] = decision
        if data is not None:
            self._data[key] = data
        if key in self._events:
            self._events[key].set()

    def get_decision(self, key: str) -> str:
        return self._decisions.get(key, "approve")

    def get_data(self, key: str):
        return self._data.get(key)

    def cleanup(self, novel_id: str) -> None:
        """Remove all checkpoint state for a finished novel."""
        for suffix in (":plot", ":chapter1", ":characters"):
            key = f"{novel_id}{suffix}"
            self._events.pop(key, None)
            self._decisions.pop(key, None)
            self._data.pop(key, None)


checkpoint_gate = CheckpointGate()


# ── Async pipeline ─────────────────────────────────────────────────────────

class AsyncNovelService:
    def __init__(self):
        self.plot_navigator = PlotNavigatorAgent()
        self.character_soul = CharacterSoulAgent()
        self.draft_master = DraftMasterAgent()
        self.final_auditor = FinalAuditorAgent()

    def _emit(self, novel_id: str, event_type: str, data: dict = None):
        broadcaster.publish(novel_id, {"type": event_type, **(data or {})})

    def _update_status(self, novel_id: str, status: str, chapter: int = None):
        db.update_novel_status(novel_id, status, chapter)
        self._emit(novel_id, "status", {"status": status, "current_chapter": chapter})

    # ── Run in thread ──────────────────────────────────────────────────────

    def _run_sync(self, novel_id: str, user_prompt: str,
                  num_chapters: int, words_per_chapter: int,
                  genre: str, loop: asyncio.AbstractEventLoop,
                  style_config: dict | None = None):
        """Blocking execution — runs in thread pool."""
        summaries: dict[int, str] = {}

        try:
            # Phase 1: Intelligence
            self._emit(novel_id, "log", {"msg": "═══ PHASE 1: INTELLIGENCE ═══"})
            self._update_status(novel_id, "navigating_plot")

            blueprint = self.plot_navigator.run(user_prompt, num_chapters=num_chapters, genre=genre)
            blueprint.words_per_chapter = words_per_chapter
            blueprint.style_config = style_config
            # Make chapter IDs unique per novel (PlotNavigator uses generic ch_001, ch_002...)
            for ch in blueprint.chapters:
                ch.id = f"{novel_id[:8]}_ch_{ch.number:03d}"

            self._update_status(novel_id, "building_characters")
            characters = self.character_soul.run(blueprint)
            blueprint.characters = characters

            # Save blueprint to DB
            bp_json = _blueprint_to_json(blueprint)
            db.update_novel_blueprint(novel_id, bp_json)

            # Checkpoint 1: plot approval
            self._update_status(novel_id, "awaiting_plot_approval")
            self._emit(novel_id, "checkpoint_plot", {
                "blueprint": _blueprint_summary(blueprint),
            })

            # Wait for frontend decision (blocking via threading.Event bridge)
            plot_key = f"{novel_id}:plot"
            bridge = _BridgeEvent(loop, plot_key)
            bridge.wait()
            decision = checkpoint_gate.get_decision(plot_key)

            if decision == "reject":
                self._update_status(novel_id, "failed")
                self._emit(novel_id, "done", {"status": "failed"})
                return

            # Phase 2: Generation
            self._emit(novel_id, "log", {"msg": "═══ PHASE 2: GENERATION ═══"})
            self._update_status(novel_id, "drafting")
            completed_chapters = []

            for chapter in blueprint.chapters:
                chapter = self._write_and_audit(
                    novel_id, chapter, blueprint, characters,
                    completed_chapters, summaries
                )

                # Generate summary then save chapter + summary atomically
                summary = self._generate_summary(novel_id, chapter)
                if summary:
                    summaries[chapter.number] = summary
                db.save_chapter_with_summary(
                    novel_id, chapter.id, chapter.number, chapter.title,
                    chapter.content, chapter.audit_passed, chapter.audit_notes,
                    summary,
                )

                # Emit chapter done
                self._emit(novel_id, "chapter_done", {
                    "number": chapter.number,
                    "title": chapter.title,
                    "word_count": len(chapter.content.split()),
                    "audit_passed": chapter.audit_passed,
                    "audit_notes": chapter.audit_notes,
                })

                # Checkpoint 2: chapter 1 approval
                if chapter.number == 1:
                    self._update_status(novel_id, "awaiting_chapter1_approval")
                    self._emit(novel_id, "checkpoint_chapter1", {
                        "preview": " ".join(chapter.content.split()[:300]),
                        "word_count": len(chapter.content.split()),
                        "audit_passed": chapter.audit_passed,
                        "audit_notes": chapter.audit_notes,
                    })

                    ch1_key = f"{novel_id}:chapter1"
                    bridge = _BridgeEvent(loop, ch1_key)
                    bridge.wait()
                    decision = checkpoint_gate.get_decision(ch1_key)

                    if decision == "regen":
                        self._emit(novel_id, "log", {"msg": "Regenerating chapter 1..."})
                        chapter = self._write_and_audit(
                            novel_id, chapter, blueprint, characters,
                            [], summaries
                        )
                        summary = self._generate_summary(novel_id, chapter)
                        if summary:
                            summaries[chapter.number] = summary
                        db.save_chapter_with_summary(
                            novel_id, chapter.id, chapter.number, chapter.title,
                            chapter.content, chapter.audit_passed, chapter.audit_notes,
                            summary,
                        )

                    self._update_status(novel_id, "drafting")

                completed_chapters.append(chapter)
                db.update_novel_status(novel_id, "drafting", chapter.number)

            # Build output markdown
            output_path = _save_markdown(novel_id, blueprint, completed_chapters)
            db.update_novel_output_path(novel_id, output_path)
            db.update_novel_status(novel_id, "completed", len(completed_chapters))

            self._emit(novel_id, "done", {
                "status": "completed",
                "output_path": output_path,
                "total_words": sum(len(ch.content.split()) for ch in completed_chapters),
            })

        except Exception as e:
            logger.error(f"Pipeline failed for novel {novel_id}: {e}", exc_info=True)
            db.update_novel_status(novel_id, "failed")
            self._emit(novel_id, "error", {"msg": str(e)})
            raise
        finally:
            checkpoint_gate.cleanup(novel_id)

    def _write_and_audit(self, novel_id, chapter, blueprint, characters,
                         previous_chapters, summaries):
        def on_progress(words: int):
            self._emit(novel_id, "chapter_progress", {
                "chapter_number": chapter.number,
                "chapter_title": chapter.title,
                "words_so_far": words,
                "target": blueprint.words_per_chapter,
            })

        for attempt in range(1, MAX_REGEN_PER_CHAPTER + 1):
            self._emit(novel_id, "log", {
                "msg": f"Writing chapter {chapter.number} (attempt {attempt})..."
            })
            chapter.content = self.draft_master.run(
                chapter, blueprint, characters, previous_chapters,
                chapter_summaries=summaries,
                on_progress=on_progress,
            )
            audit_result = self.final_auditor.run(chapter, characters)
            chapter.audit_passed = audit_result.get("passed", False)
            chapter.audit_notes = audit_result.get("summary", "")

            if chapter.audit_passed:
                break
            if attempt < MAX_REGEN_PER_CHAPTER:
                self._emit(novel_id, "log", {
                    "msg": f"Audit failed — regenerating (attempt {attempt + 1}/{MAX_REGEN_PER_CHAPTER})..."
                })
        return chapter

    def _continue_sync(self, novel_id: str, num_chapters: int, genre_override: str,
                       loop: asyncio.AbstractEventLoop):
        """Continue an existing novel — runs in thread pool."""
        try:
            row = db.get_novel(novel_id)
            if not row or not row["blueprint_json"]:
                self._emit(novel_id, "error", {"msg": "Novel or blueprint not found"})
                return

            blueprint = _json_to_blueprint(row["blueprint_json"])
            genre = genre_override or blueprint.genre
            existing_chapter_rows = db.get_chapters(novel_id)
            summaries = db.get_summaries(novel_id)
            start_chapter = len(existing_chapter_rows) + 1

            self._emit(novel_id, "log", {"msg": "═══ VIẾT TIẾP ═══"})
            self._update_status(novel_id, "navigating_plot")

            # Build existing summary from DB summaries
            existing_summary = "\n".join(
                summaries.get(r["number"], f"Chương {r['number']}: {r['title']}")
                for r in existing_chapter_rows
            )
            # Get last cliffhanger from blueprint
            last_cliffhanger = ""
            if blueprint.chapters:
                last_ch = max(blueprint.chapters, key=lambda c: c.number)
                last_cliffhanger = last_ch.ending_cliffhanger

            # 1. Plot continuation
            new_chapter_objects = self.plot_navigator.run_continuation(
                blueprint=blueprint,
                existing_summary=existing_summary,
                last_cliffhanger=last_cliffhanger,
                num_new_chapters=num_chapters,
                start_chapter=start_chapter,
                genre=genre,
            )
            for ch in new_chapter_objects:
                ch.id = f"{novel_id[:8]}_ch_{ch.number:03d}"

            # 2. Character additions
            self._update_status(novel_id, "building_characters")
            proposed_new_chars = self.character_soul.run_additions(blueprint, new_chapter_objects)

            self._emit(novel_id, "checkpoint_characters", {
                "characters": [_char_to_dict(c) for c in proposed_new_chars]
            })

            char_key = f"{novel_id}:characters"
            _BridgeEvent(loop, char_key).wait()
            approved_dicts = checkpoint_gate.get_data(char_key) or []
            approved_new_chars = []
            for c in approved_dicts:
                c = dict(c)
                rels = [CharacterRelationship(**r) for r in c.pop("relationships", [])]
                approved_new_chars.append(CharacterProfile(**c, relationships=rels))

            # Merge into blueprint and save
            all_characters = blueprint.characters + approved_new_chars
            blueprint.characters = all_characters
            blueprint.chapters.extend(new_chapter_objects)
            blueprint.genre = genre
            blueprint.target_chapters = len(blueprint.chapters)
            db.update_novel_blueprint(novel_id, _blueprint_to_json(blueprint))

            # 3. Plot checkpoint
            self._update_status(novel_id, "awaiting_plot_approval")
            self._emit(novel_id, "checkpoint_plot", {"blueprint": _blueprint_summary(blueprint)})

            plot_key = f"{novel_id}:plot"
            _BridgeEvent(loop, plot_key).wait()
            if checkpoint_gate.get_decision(plot_key) == "reject":
                self._update_status(novel_id, "completed")
                self._emit(novel_id, "done", {"status": "completed"})
                return

            # 4. Generate new chapters
            self._emit(novel_id, "log", {"msg": "═══ VIẾT CHƯƠNG MỚI ═══"})
            self._update_status(novel_id, "drafting")

            # Build prev_chapters with content from DB
            ch_content_map = {r["number"]: r["content"] for r in existing_chapter_rows}
            prev_with_content = []
            for ch in blueprint.chapters:
                if ch.number in ch_content_map:
                    ch.content = ch_content_map[ch.number]
                    prev_with_content.append(ch)

            for chapter in new_chapter_objects:
                chapter = self._write_and_audit(
                    novel_id, chapter, blueprint, all_characters, prev_with_content, summaries,
                )
                summary = self._generate_summary(novel_id, chapter)
                if summary:
                    summaries[chapter.number] = summary
                db.save_chapter_with_summary(
                    novel_id, chapter.id, chapter.number, chapter.title,
                    chapter.content, chapter.audit_passed, chapter.audit_notes,
                    summary,
                )
                self._emit(novel_id, "chapter_done", {
                    "number": chapter.number, "title": chapter.title,
                    "word_count": len(chapter.content.split()), "audit_passed": chapter.audit_passed,
                    "audit_notes": chapter.audit_notes,
                })
                prev_with_content.append(chapter)
                db.update_novel_status(novel_id, "drafting", chapter.number)

            # Save updated markdown
            all_ch_rows = db.get_chapters(novel_id)
            ch_content_map.update({r["number"]: r["content"] for r in all_ch_rows})
            all_chs_for_md = []
            for ch in sorted(blueprint.chapters, key=lambda c: c.number):
                if ch.number in ch_content_map:
                    ch.content = ch_content_map[ch.number]
                    all_chs_for_md.append(ch)

            output_path = _save_markdown(novel_id, blueprint, all_chs_for_md)
            db.update_novel_output_path(novel_id, output_path)
            total_words = sum(len(r["content"].split()) for r in all_ch_rows)
            db.update_novel_status(novel_id, "completed", len(all_ch_rows))
            self._emit(novel_id, "done", {
                "status": "completed", "output_path": output_path, "total_words": total_words,
            })

        except Exception as e:
            logger.error(f"Continue pipeline failed for novel {novel_id}: {e}", exc_info=True)
            db.update_novel_status(novel_id, "failed")
            self._emit(novel_id, "error", {"msg": f"Continue failed: {e}"})
            raise
        finally:
            checkpoint_gate.cleanup(novel_id)

    def _regen_sync(self, novel_id: str, chapter_number: int,
                    loop: asyncio.AbstractEventLoop):
        """Regen a single chapter post-completion — runs in thread pool."""
        try:
            row = db.get_novel(novel_id)
            if not row or not row["blueprint_json"]:
                self._emit(novel_id, "error", {"msg": "Novel or blueprint not found"})
                return

            blueprint = _json_to_blueprint(row["blueprint_json"])
            characters = blueprint.characters

            chapter_obj = next(
                (ch for ch in blueprint.chapters if ch.number == chapter_number), None
            )
            if chapter_obj is None:
                self._emit(novel_id, "error", {"msg": f"Chapter {chapter_number} not in blueprint"})
                return

            # Restore existing content so _write_and_audit has a starting point
            existing = db.get_chapter(novel_id, chapter_number)
            if existing:
                chapter_obj.content = existing["content"]
                chapter_obj.audit_passed = bool(existing["audit_passed"])
                chapter_obj.audit_notes = existing["audit_notes"]

            # Build previous chapters list with content from DB
            all_rows = {r["number"]: r for r in db.get_chapters(novel_id)}
            previous_chapters = []
            for ch in blueprint.chapters:
                if ch.number < chapter_number and ch.number in all_rows:
                    ch.content = all_rows[ch.number]["content"]
                    previous_chapters.append(ch)

            summaries = db.get_summaries(novel_id)

            self._emit(novel_id, "log", {"msg": f"Regenerating chapter {chapter_number}..."})
            self._emit(novel_id, "regen_start", {"chapter_number": chapter_number})

            chapter_obj = self._write_and_audit(
                novel_id, chapter_obj, blueprint, characters, previous_chapters, summaries,
            )

            summary = self._generate_summary(novel_id, chapter_obj)
            db.save_chapter_with_summary(
                novel_id, chapter_obj.id, chapter_obj.number, chapter_obj.title,
                chapter_obj.content, chapter_obj.audit_passed, chapter_obj.audit_notes,
                summary,
            )

            # Rebuild markdown with updated chapter content
            all_ch_rows = db.get_chapters(novel_id)
            ch_content_map = {r["number"]: r["content"] for r in all_ch_rows}
            chapters_for_md = []
            for ch in sorted(blueprint.chapters, key=lambda c: c.number):
                if ch.number in ch_content_map:
                    ch.content = ch_content_map[ch.number]
                    chapters_for_md.append(ch)
            output_path = _save_markdown(novel_id, blueprint, chapters_for_md)
            db.update_novel_output_path(novel_id, output_path)

            self._emit(novel_id, "regen_done", {
                "chapter_number": chapter_number,
                "title": chapter_obj.title,
                "word_count": len(chapter_obj.content.split()),
                "audit_passed": chapter_obj.audit_passed,
                "audit_notes": chapter_obj.audit_notes,
            })

        except Exception as e:
            logger.error(f"Regen failed for novel {novel_id} ch{chapter_number}: {e}", exc_info=True)
            self._emit(novel_id, "error", {"msg": f"Regen failed: {e}"})
            raise

    def _generate_summary(self, novel_id: str, chapter) -> str:
        self._emit(novel_id, "log", {"msg": f"Summarizing chapter {chapter.number}..."})
        try:
            # Lấy đầu + cuối để không mất context mở đầu chương
            content = chapter.content
            if len(content) > 4000:
                content = content[:2000] + "\n…\n" + content[-2000:]
            prompt = CHAPTER_SUMMARY_PROMPT.format(
                chapter_number=chapter.number,
                chapter_title=chapter.title,
                chapter_content=content,
            )
            return build_adapter("summarizer").generate(prompt, max_tokens=512).strip()
        except Exception as e:
            self._emit(novel_id, "log", {"msg": f"Summary failed (non-critical): {e}"})
            return ""


# ── Bridge: asyncio.Event → threading wait ────────────────────────────────

class _BridgeEvent:
    """Lets a background thread block until an asyncio.Event fires."""

    def __init__(self, loop: asyncio.AbstractEventLoop, key: str):
        import threading
        self._done = threading.Event()
        self._loop = loop
        self._key = key
        # Register: when asyncio Event fires, set threading.Event
        asyncio_event = checkpoint_gate.create(key)
        loop.call_soon_threadsafe(self._attach, asyncio_event)

    def _attach(self, asyncio_event: asyncio.Event):
        async def _watcher():
            await asyncio_event.wait()
            self._done.set()

        asyncio.create_task(_watcher())

    def wait(self, timeout: int = 1800) -> None:
        if not self._done.wait(timeout=timeout):
            raise TimeoutError(f"Checkpoint '{self._key}' timed out after {timeout}s — pipeline aborted")


# ── Helpers ───────────────────────────────────────────────────────────────

def _char_to_dict(c: CharacterProfile) -> dict:
    from dataclasses import asdict
    return asdict(c)


def _json_to_blueprint(blueprint_json: str) -> StoryBlueprint:
    """Deserialize blueprint JSON (saved by _blueprint_to_json) back to typed objects."""
    try:
        data = json.loads(blueprint_json)
        chapters = [Chapter(**ch) for ch in data.get("chapters", [])]
        characters = []
        for c in data.get("characters", []):
            rels = [CharacterRelationship(**r) for r in c.pop("relationships", [])]
            characters.append(CharacterProfile(**c, relationships=rels))
        return StoryBlueprint(
            title=data["title"],
            premise=data["premise"],
            genre=data.get("genre", "isekai"),
            target_chapters=data.get("target_chapters", len(chapters)),
            words_per_chapter=data.get("words_per_chapter", 4500),
            world_summary=data.get("world_summary", ""),
            chapters=chapters,
            characters=characters,
            style_config=data.get("style_config"),
        )
    except (KeyError, TypeError, json.JSONDecodeError) as e:
        raise ValueError(f"Blueprint deserialization failed: {e}") from e


def _blueprint_to_json(bp: StoryBlueprint) -> str:
    from dataclasses import asdict
    return json.dumps(asdict(bp), ensure_ascii=False)


def _blueprint_summary(bp: StoryBlueprint) -> dict:
    return {
        "title": bp.title,
        "premise": bp.premise,
        "world_summary": bp.world_summary,
        "chapters": [
            {
                "number": ch.number,
                "title": ch.title,
                "pov_character": ch.pov_character,
                "opening_hook": ch.opening_hook,
                "ending_cliffhanger": ch.ending_cliffhanger,
            }
            for ch in bp.chapters
        ],
        "characters": [
            {
                "name": c.name,
                "role": c.role,
                "personality_traits": c.personality_traits[:2],
                "core_value": c.core_value,
                "fear": c.fear,
            }
            for c in bp.characters
        ],
    }


def _save_markdown(novel_id: str, blueprint: StoryBlueprint, chapters) -> str:
    from pathlib import Path
    from datetime import datetime

    out_dir = Path(__file__).parent.parent / "output"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = blueprint.title[:40].replace("/", "-").replace("\\", "-")
    path = out_dir / f"{ts}_{safe_title}.md"

    lines = [f"# {blueprint.title}\n", f"*{blueprint.premise}*\n\n"]
    for ch in chapters:
        lines.append(f"## Chương {ch.number}: {ch.title}\n\n")
        lines.append(ch.content)
        lines.append("\n\n---\n\n")

    path.write_text("".join(lines), encoding="utf-8")
    return str(path)


# ── Public API ─────────────────────────────────────────────────────────────

_service = AsyncNovelService()


def start_novel_pipeline(novel_id: str, user_prompt: str,
                          num_chapters: int, words_per_chapter: int,
                          genre: str, loop: asyncio.AbstractEventLoop,
                          style_config: dict | None = None):
    """Submit pipeline to thread pool — non-blocking from async context."""
    _executor.submit(
        _service._run_sync,
        novel_id, user_prompt, num_chapters, words_per_chapter, genre, loop, style_config,
    )


def start_regen_chapter(novel_id: str, chapter_number: int,
                         loop: asyncio.AbstractEventLoop):
    """Submit single-chapter regen to thread pool — non-blocking from async context."""
    _executor.submit(_service._regen_sync, novel_id, chapter_number, loop)


def start_continue_pipeline(novel_id: str, num_chapters: int, genre: str,
                             loop: asyncio.AbstractEventLoop):
    """Submit continuation pipeline to thread pool — non-blocking from async context."""
    _executor.submit(_service._continue_sync, novel_id, num_chapters, genre, loop)
