import logging
from core.ai_adapter import build_adapter, parse_json_response
from core.models import StoryBlueprint, Chapter

logger = logging.getLogger(__name__)
from core.prompts.plot_prompts import PLOT_NAVIGATOR_PROMPT, PLOT_CONTINUATION_PROMPT, GENRE_PLOT_HINTS, GENRE_DISPLAY_NAMES, GENRE_STYLES, ISEKAI_GENRE_STYLE
from config import DEFAULT_CHAPTERS, DEFAULT_GENRE


class PlotNavigatorAgent:
    def run(self, user_prompt: str, num_chapters: int = DEFAULT_CHAPTERS,
            genre: str = DEFAULT_GENRE) -> StoryBlueprint:
        ai = build_adapter("plot_navigator")
        logger.info("Generating plot...")
        prompt = PLOT_NAVIGATOR_PROMPT.format(
            user_prompt=user_prompt,
            num_chapters=num_chapters,
            genre_name=GENRE_DISPLAY_NAMES.get(genre, genre),
            genre_hints=GENRE_PLOT_HINTS.get(genre, GENRE_PLOT_HINTS["isekai"]),
        )
        response = ai.generate(prompt, max_tokens=8192, json_mode=False)
        data = parse_json_response(response)

        chapters = []
        for ch_data in data.get("chapters", []):
            chapters.append(Chapter(
                id=f"ch_{ch_data['number']:03d}",
                number=ch_data["number"],
                title=ch_data["title"],
                pov_character=ch_data["pov_character"],
                opening_hook=ch_data["opening_hook"],
                ending_cliffhanger=ch_data["ending_cliffhanger"],
                outline_beats=ch_data.get("outline_beats", []),
            ))

        blueprint = StoryBlueprint(
            title=data["title"],
            premise=data["premise"],
            world_summary=data.get("world_summary", ""),
            genre=genre,
            target_chapters=num_chapters,
            chapters=chapters,
        )
        logger.info(f"Done: '{blueprint.title}', {len(chapters)} chapters planned.")
        return blueprint

    def run_continuation(self, blueprint: StoryBlueprint, existing_summary: str,
                         last_cliffhanger: str, num_new_chapters: int,
                         start_chapter: int, genre: str) -> list[Chapter]:
        ai = build_adapter("plot_navigator")
        logger.info(f"Generating continuation chapters {start_chapter}+...")
        end_chapter = start_chapter + num_new_chapters - 1
        prompt = PLOT_CONTINUATION_PROMPT.format(
            title=blueprint.title,
            existing_count=start_chapter - 1,
            num_new_chapters=num_new_chapters,
            start_chapter=start_chapter,
            end_chapter=end_chapter,
            genre_name=GENRE_DISPLAY_NAMES.get(genre, genre),
            genre_hints=GENRE_PLOT_HINTS.get(genre, GENRE_PLOT_HINTS["isekai"]),
            premise=blueprint.premise,
            existing_summary=existing_summary,
            last_cliffhanger=last_cliffhanger,
        )
        response = ai.generate(prompt, max_tokens=8192, json_mode=False)
        data = parse_json_response(response)

        chapters = []
        for ch_data in data.get("chapters", []):
            chapters.append(Chapter(
                id=f"ch_{ch_data['number']:03d}",
                number=ch_data["number"],
                title=ch_data["title"],
                pov_character=ch_data["pov_character"],
                opening_hook=ch_data["opening_hook"],
                ending_cliffhanger=ch_data["ending_cliffhanger"],
                outline_beats=ch_data.get("outline_beats", []),
            ))
        logger.info(f"Continuation done: {len(chapters)} new chapters planned.")
        return chapters

