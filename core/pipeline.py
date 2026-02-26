from core.models import NovelProject, NovelStatus
from core.agents.plot_navigator import PlotNavigatorAgent
from core.agents.character_soul import CharacterSoulAgent
from core.agents.draft_master import DraftMasterAgent
from core.agents.final_auditor import FinalAuditorAgent
from core.ai_adapter import GeminiAdapter
from core.prompts.writer_prompts import CHAPTER_SUMMARY_PROMPT
from config import DEFAULT_CHAPTERS, DEFAULT_WORDS_PER_CHAPTER, FINAL_AUDITOR_MODEL

MAX_REGEN_PER_CHAPTER = 3


class LightNovelPipeline:
    def __init__(self):
        self.plot_navigator = PlotNavigatorAgent()
        self.character_soul = CharacterSoulAgent()
        self.draft_master = DraftMasterAgent()
        self.final_auditor = FinalAuditorAgent()
        self._summarizer = GeminiAdapter(FINAL_AUDITOR_MODEL)
        # chapter_number → summary string
        self._summaries: dict[int, str] = {}

    def run(self, project: NovelProject) -> NovelProject:
        # ── Phase 1: Intelligence ──────────────────────────────
        print("\n═══ PHASE 1: INTELLIGENCE ═══")

        project.status = NovelStatus.NAVIGATING_PLOT
        blueprint = self.plot_navigator.run(
            project.user_prompt,
            num_chapters=DEFAULT_CHAPTERS,
            genre=DEFAULT_GENRE,
        )
        blueprint.words_per_chapter = DEFAULT_WORDS_PER_CHAPTER
        project.blueprint = blueprint

        project.status = NovelStatus.BUILDING_CHARACTERS
        characters = self.character_soul.run(blueprint)
        blueprint.characters = characters

        # Checkpoint 1: Approve plot
        project.status = NovelStatus.AWAITING_PLOT_APPROVAL
        if not self._checkpoint_approve_plot(blueprint):
            project.status = NovelStatus.FAILED
            return project

        # ── Phase 2: Generation ───────────────────────────────
        print("\n═══ PHASE 2: GENERATION ═══")
        project.status = NovelStatus.DRAFTING
        completed_chapters = []

        for chapter in blueprint.chapters:
            chapter = self._write_and_audit_chapter(
                chapter, blueprint, characters, completed_chapters
            )

            # Auto-generate summary after each chapter
            self._generate_summary(chapter)

            # Checkpoint 2: Approve chapter 1 only
            if chapter.number == 1:
                project.status = NovelStatus.AWAITING_CHAPTER1_APPROVAL
                chapter = self._checkpoint_approve_chapter1(
                    chapter, blueprint, characters, completed_chapters
                )
                project.status = NovelStatus.DRAFTING

            completed_chapters.append(chapter)
            project.current_chapter = chapter.number

        blueprint.chapters = completed_chapters
        project.status = NovelStatus.COMPLETED
        return project

    def _write_and_audit_chapter(self, chapter, blueprint, characters, previous_chapters):
        for attempt in range(1, MAX_REGEN_PER_CHAPTER + 1):
            chapter.content = self.draft_master.run(
                chapter, blueprint, characters, previous_chapters,
                chapter_summaries=self._summaries,
            )
            audit_result = self.final_auditor.run(chapter, characters)
            chapter.audit_passed = audit_result.get("passed", False)
            chapter.audit_notes = audit_result.get("summary", "")

            if chapter.audit_passed:
                break
            if attempt < MAX_REGEN_PER_CHAPTER:
                print(f"  [Pipeline] Audit failed — regenerating chapter {chapter.number} (attempt {attempt + 1}/{MAX_REGEN_PER_CHAPTER})...")
            else:
                print(f"  [Pipeline] Audit failed after {MAX_REGEN_PER_CHAPTER} attempts — continuing.")

        return chapter

    def _generate_summary(self, chapter):
        """Auto-generate ~150 word summary after each chapter."""
        print(f"  [Pipeline] Summarizing chapter {chapter.number}...")
        try:
            prompt = CHAPTER_SUMMARY_PROMPT.format(
                chapter_number=chapter.number,
                chapter_title=chapter.title,
                chapter_content=chapter.content[-4000:],  # Last 4000 chars sufficient
            )
            summary = self._summarizer.generate(prompt, max_tokens=512)
            self._summaries[chapter.number] = summary.strip()
        except Exception as e:
            print(f"  [Pipeline] Summary generation failed (non-critical): {e}")

    def _checkpoint_approve_plot(self, blueprint) -> bool:
        print("\n" + "─" * 60)
        print(f"[CHECKPOINT 1] Plot approval")
        print(f"  Title   : {blueprint.title}")
        print(f"  Premise : {blueprint.premise}")
        print(f"  World   : {blueprint.world_summary}")
        print(f"\n  Chapters:")
        for ch in blueprint.chapters:
            print(f"    {ch.number}. {ch.title} (POV: {ch.pov_character})")
            print(f"       Hook: {ch.opening_hook}")
            print(f"       Cliffhanger: {ch.ending_cliffhanger}")
        print(f"\n  Characters:")
        for char in blueprint.characters:
            print(f"    - {char.name} ({char.role}): {', '.join(char.personality_traits[:2])}")
        print("─" * 60)

        while True:
            choice = input("Approve plot? [y/n]: ").strip().lower()
            if choice == "y":
                return True
            if choice == "n":
                print("Pipeline cancelled.")
                return False

    def _checkpoint_approve_chapter1(self, chapter, blueprint, characters, previous_chapters):
        print("\n" + "─" * 60)
        print(f"[CHECKPOINT 2] Chapter 1 approval")
        print(f"  Audit: {'PASSED' if chapter.audit_passed else 'FAILED'} — {chapter.audit_notes}")
        print(f"  Word count: {len(chapter.content.split())} words")
        print(f"\n--- CHAPTER 1 PREVIEW (first 300 words) ---")
        words = chapter.content.split()
        print(" ".join(words[:300]) + ("..." if len(words) > 300 else ""))
        print("─" * 60)

        while True:
            choice = input("Approve chapter 1? [y=approve / r=regenerate / s=skip]: ").strip().lower()
            if choice in ("y", "s"):
                return chapter
            if choice == "r":
                print("  Regenerating chapter 1...")
                chapter = self._write_and_audit_chapter(
                    chapter, blueprint, characters, previous_chapters
                )
                self._generate_summary(chapter)
                words = chapter.content.split()
                print(f"\n  Regenerated: {len(words)} words. Audit: {'PASSED' if chapter.audit_passed else 'FAILED'}")
                print("  Preview: " + " ".join(words[:150]) + "...")
