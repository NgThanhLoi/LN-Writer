import logging
from core.ai_adapter import build_adapter, parse_json_response
from core.models import CharacterProfile, CharacterRelationship, Chapter, StoryBlueprint

logger = logging.getLogger(__name__)
from core.prompts.character_prompts import CHARACTER_SOUL_PROMPT, CHARACTER_ADDITIONS_PROMPT


class CharacterSoulAgent:
    def run(self, blueprint: StoryBlueprint) -> list[CharacterProfile]:
        ai = build_adapter("character_soul")
        logger.info("Building characters...")
        chapters_outline = self._format_chapters_outline(blueprint)
        prompt = CHARACTER_SOUL_PROMPT.format(
            premise=blueprint.premise,
            world_summary=blueprint.world_summary,
            num_chapters=blueprint.target_chapters,
            chapters_outline=chapters_outline,
        )
        response = ai.generate(prompt, max_tokens=8192, json_mode=False)
        data = parse_json_response(response)

        characters = []
        for ch_data in data.get("characters", []):
            characters.append(CharacterProfile(
                id=ch_data["id"],
                name=ch_data["name"],
                role=ch_data["role"],
                personality_traits=ch_data.get("personality_traits", []),
                speech_pattern=ch_data.get("speech_pattern", ""),
                backstory=ch_data.get("backstory", ""),
                goals=ch_data.get("goals", []),
                current_state=ch_data.get("current_state", ""),
                core_value=ch_data.get("core_value", ""),
                fear=ch_data.get("fear", ""),
                weakness=ch_data.get("weakness", ""),
                catchphrase=ch_data.get("catchphrase", ""),
                relationships=[
                    CharacterRelationship(**r)
                    for r in ch_data.get("relationships", [])
                ],
            ))

        logger.info(f"Done: {len(characters)} characters created.")
        return characters

    def run_additions(self, blueprint: StoryBlueprint,
                      new_chapters: list[Chapter]) -> list[CharacterProfile]:
        ai = build_adapter("character_soul")
        logger.info("Proposing new characters...")
        existing = "\n".join(
            f"- {c.name} ({c.role}): {', '.join(c.personality_traits[:2])}"
            for c in blueprint.characters
        )
        new_outline = "\n".join(
            f"Chương {ch.number}: {ch.title} — {', '.join(ch.outline_beats[:2])}"
            for ch in new_chapters
        )
        prompt = CHARACTER_ADDITIONS_PROMPT.format(
            existing_characters=existing,
            new_chapters_outline=new_outline,
        )
        response = ai.generate(prompt, max_tokens=4096, json_mode=False)
        data = parse_json_response(response)

        characters = []
        for ch_data in data.get("characters", []):
            characters.append(CharacterProfile(
                id=ch_data["id"],
                name=ch_data["name"],
                role=ch_data["role"],
                personality_traits=ch_data.get("personality_traits", []),
                speech_pattern=ch_data.get("speech_pattern", ""),
                backstory=ch_data.get("backstory", ""),
                goals=ch_data.get("goals", []),
                current_state=ch_data.get("current_state", ""),
                core_value=ch_data.get("core_value", ""),
                fear=ch_data.get("fear", ""),
                weakness=ch_data.get("weakness", ""),
                catchphrase=ch_data.get("catchphrase", ""),
                relationships=[
                    CharacterRelationship(**r)
                    for r in ch_data.get("relationships", [])
                ],
            ))
        logger.info(f"Proposed {len(characters)} new character(s).")
        return characters

    def _format_chapters_outline(self, blueprint: StoryBlueprint) -> str:
        lines = []
        for ch in blueprint.chapters:
            lines.append(f"Chương {ch.number}: {ch.title}")
            lines.append(f"  Beats: {', '.join(ch.outline_beats[:2])}...")
        return "\n".join(lines)

