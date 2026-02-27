import logging
import time
from core.ai_adapter import build_adapter

logger = logging.getLogger(__name__)
from core.models import Chapter, StoryBlueprint, CharacterProfile
from core.prompts.writer_prompts import DRAFT_MASTER_PROMPT, PREVIOUS_CONTEXT_TEMPLATE
from core.prompts.plot_prompts import GENRE_STYLES, ISEKAI_GENRE_STYLE

MIN_WORD_RATIO = 0.80  # Auto-regen if below 80% of target

_TONE_MAP = {"light": "Nhẹ nhàng, vui tươi, hài hước", "neutral": "Trung tính, cân bằng", "tense": "Căng thẳng, hồi hộp, kịch tính"}
_DIAL_MAP = {"low": "~30% hội thoại, tập trung mô tả", "medium": "~45% hội thoại", "high": "~60% hội thoại, nhịp độ nhanh"}


def _build_style_block(sc: dict) -> str:
    lines = ["\n\n[STYLE OVERRIDE — tuân thủ nghiêm ngặt]"]
    lines.append(f"- Tone: {_TONE_MAP.get(sc.get('tone', 'neutral'), 'Trung tính')}")
    lines.append(f"- Hội thoại: {_DIAL_MAP.get(sc.get('dialogue_ratio', 'medium'), '~45% hội thoại')}")
    if sc.get("custom_note"):
        lines.append(f"- Lưu ý đặc biệt: {sc['custom_note']}")
    return "\n".join(lines)


_PROGRESS_EVERY = 200  # emit progress every ~200 words accumulated


class DraftMasterAgent:

    def run(
        self,
        chapter: Chapter,
        blueprint: StoryBlueprint,
        characters: list[CharacterProfile],
        previous_chapters: list[Chapter],
        chapter_summaries: dict[int, str] | None = None,
        on_progress=None,
    ) -> str:
        logger.info(f"Writing chapter {chapter.number}: '{chapter.title}'...")

        content = self._write(chapter, blueprint, characters, previous_chapters, chapter_summaries,
                              on_progress=on_progress)

        # Word count check — auto regen once if below 80%
        word_count = len(content.split())
        target = blueprint.words_per_chapter
        if word_count < target * MIN_WORD_RATIO:
            logger.info(f"Word count {word_count} < {int(target * MIN_WORD_RATIO)} target — regenerating...")
            content = self._write(
                chapter, blueprint, characters, previous_chapters, chapter_summaries,
                on_progress=on_progress,
                extra_instruction=f"QUAN TRỌNG: Bản trước chỉ có {word_count} từ, quá ngắn. Lần này BẮT BUỘC viết đủ {target} từ. Mở rộng tất cả các scene."
            )
            word_count = len(content.split())

        logger.info(f"Done: {word_count} words.")
        return content

    def _write(
        self,
        chapter: Chapter,
        blueprint: StoryBlueprint,
        characters: list[CharacterProfile],
        previous_chapters: list[Chapter],
        chapter_summaries: dict[int, str] | None,
        extra_instruction: str = "",
        on_progress=None,
    ) -> str:
        characters_info = self._format_characters(characters)
        outline_beats = "\n".join(f"  - {beat}" for beat in chapter.outline_beats)
        previous_context = self._build_previous_context(previous_chapters, chapter_summaries)

        genre_style = GENRE_STYLES.get(blueprint.genre, ISEKAI_GENRE_STYLE)
        prompt = DRAFT_MASTER_PROMPT.format(
            chapter_number=chapter.number,
            title=blueprint.title,
            genre_style=genre_style,
            premise=blueprint.premise,
            world_summary=blueprint.world_summary,
            characters_info=characters_info,
            chapter_title=chapter.title,
            pov_character=chapter.pov_character,
            opening_hook=chapter.opening_hook,
            ending_cliffhanger=chapter.ending_cliffhanger,
            outline_beats=outline_beats,
            previous_context=previous_context,
            target_words=blueprint.words_per_chapter,
        )

        if blueprint.style_config:
            prompt += _build_style_block(blueprint.style_config)

        if extra_instruction:
            prompt += f"\n\n{extra_instruction}"

        # Warn if prompt is very long (rough estimate: ~3 chars/token for Vietnamese)
        estimated_tokens = len(prompt) // 3
        if estimated_tokens > 30000:
            logger.warning(f"Chapter {chapter.number} prompt is large (~{estimated_tokens} est. tokens) — may approach context limits")

        # Stream and accumulate — retry up to 2 times if stream fails
        # Each retry resets all state so consumer never sees partial + full mix
        adapter = build_adapter("draft_master")
        last_error = None
        chunks: list[str] = []
        for attempt in range(1, 3):
            chunks = []
            word_count = 0
            last_reported = 0
            try:
                for chunk in adapter.generate_stream(prompt, max_tokens=16384):
                    chunks.append(chunk)
                    word_count += len(chunk.split())
                    if on_progress and word_count - last_reported >= _PROGRESS_EVERY:
                        on_progress(word_count)
                        last_reported = word_count
                break  # stream completed successfully
            except Exception as e:
                last_error = e
                if attempt < 2:
                    logger.warning(f"Stream attempt {attempt} failed, retrying... ({e})")
                    time.sleep(2)
        else:
            raise RuntimeError(f"Stream failed after 2 attempts: {last_error}") from last_error
        return "".join(chunks)

    def _format_characters(self, characters: list[CharacterProfile]) -> str:
        lines = []
        for char in characters:
            traits = ", ".join(char.personality_traits)
            char_block = [
                f"- {char.name} ({char.role}): {traits}",
                f"  Cách nói: {char.speech_pattern}",
                f"  Trạng thái hiện tại: {char.current_state}"
            ]

            # Thêm thông tin tầng sâu cho inner monologue và conflict
            if char.core_value:
                char_block.append(f"  Giá trị cốt lõi: {char.core_value}")
            if char.fear:
                char_block.append(f"  Nỗi sợ: {char.fear}")
            if char.weakness:
                char_block.append(f"  Điểm yếu: {char.weakness}")
            if char.catchphrase:
                char_block.append(f"  Câu nói đặc trưng: '{char.catchphrase}'")

            # Thêm relationships với characters khác
            if char.relationships:
                rel_lines = []
                for rel in char.relationships:
                    rel_lines.append(f"    + {rel.target_name} ({rel.type}): {rel.dynamic}")
                char_block.append("  Quan hệ:")
                char_block.extend(rel_lines)

            lines.append("\n".join(char_block))
        return "\n\n".join(lines)

    def _build_previous_context(
        self,
        previous_chapters: list[Chapter],
        chapter_summaries: dict[int, str] | None,
    ) -> str:
        if not previous_chapters:
            return ""

        # Tail content: last 500 words of most recent chapter
        last_ch = previous_chapters[-1]
        words = last_ch.content.split()
        tail_content = " ".join(words[-500:]) if len(words) > 500 else last_ch.content

        # Summaries: up to 2 previous chapters from DB, fallback to raw words
        summaries = []
        for ch in previous_chapters[-2:]:
            if chapter_summaries and ch.number in chapter_summaries:
                summaries.append(f"[Ch.{ch.number} — {ch.title}]: {chapter_summaries[ch.number]}")
            else:
                # Fallback: first 80 words
                raw = " ".join(ch.content.split()[:80])
                summaries.append(f"[Ch.{ch.number} — {ch.title}]: {raw}...")

        return PREVIOUS_CONTEXT_TEMPLATE.format(
            tail_content=tail_content,
            chapter_summaries="\n".join(summaries),
        )
