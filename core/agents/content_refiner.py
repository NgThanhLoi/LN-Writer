import logging
from core.ai_adapter import build_adapter
from core.models import Chapter, StoryBlueprint
from core.prompts.refiner_prompts import CONTENT_REFINER_PROMPT, GENRE_REFINEMENT_HINTS

logger = logging.getLogger(__name__)

_FALLBACK_GENRE = "isekai"


class ContentRefinerAgent:
    """Quality mode: rewrite chapter prose without changing plot or characters."""

    def run(self, chapter: Chapter, blueprint: StoryBlueprint) -> str:
        hints = GENRE_REFINEMENT_HINTS.get(blueprint.genre, GENRE_REFINEMENT_HINTS[_FALLBACK_GENRE])
        prompt = CONTENT_REFINER_PROMPT.format(
            genre_refinement_hints=hints,
            chapter_number=chapter.number,
            chapter_title=chapter.title,
            draft_content=chapter.content,
        )

        estimated_tokens = len(prompt) // 3
        if estimated_tokens > 30000:
            logger.warning(
                f"ContentRefiner chapter {chapter.number} prompt is large "
                f"(~{estimated_tokens} est. tokens)"
            )

        logger.info(f"Refining prose for chapter {chapter.number}...")
        ai = build_adapter("content_refiner")
        refined = ai.generate(prompt, max_tokens=16384)

        # Sanity check: if refined output is drastically shorter, keep original
        original_words = len(chapter.content.split())
        refined_words = len(refined.split())
        if refined_words < original_words * 0.5:
            logger.warning(
                f"ContentRefiner output too short ({refined_words} vs {original_words} words) — "
                "keeping original draft"
            )
            return chapter.content

        logger.info(f"Refined chapter {chapter.number}: {original_words} → {refined_words} words")
        return refined
