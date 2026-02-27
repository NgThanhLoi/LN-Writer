import json
import logging
from core.ai_adapter import build_adapter, parse_json_response

logger = logging.getLogger(__name__)
from core.models import Chapter, CharacterProfile
from core.prompts.auditor_prompts import AUDITOR_PROMPT


class FinalAuditorAgent:
    def run(self, chapter: Chapter, characters: list[CharacterProfile]) -> dict:
        ai = build_adapter("final_auditor")
        logger.info(f"Auditing chapter {chapter.number}...")
        character_profiles = self._format_profiles(characters)
        prompt = AUDITOR_PROMPT.format(
            character_profiles=character_profiles,
            chapter_number=chapter.number,
            chapter_content=chapter.content,
        )
        response = ai.generate(prompt, max_tokens=2048)
        try:
            result = parse_json_response(response)
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"Could not parse audit response for chapter {chapter.number} — treating as FAILED.")
            result = {"passed": False, "issues": [], "summary": "Auditor parse error — chapter will be regenerated."}

        passed = result.get("passed", False)
        issues = result.get("issues", [])
        summary = result.get("summary", "")

        if passed:
            logger.info(f"Chapter {chapter.number} PASSED. {summary}")
        else:
            logger.info(f"Chapter {chapter.number} FAILED. {len(issues)} issue(s) found.")
            for issue in issues:
                logger.info(f"  [{issue.get('issue_type')}] {issue.get('character')}: {issue.get('description')}")

        return result

    def _format_profiles(self, characters: list[CharacterProfile]) -> str:
        lines = []
        for char in characters:
            traits = ", ".join(char.personality_traits)
            parts = [
                f"**{char.name}** ({char.role})",
                f"  Tính cách: {traits}",
                f"  Cách nói: {char.speech_pattern}",
                f"  Backstory: {char.backstory}",
            ]
            if char.core_value:
                parts.append(f"  Giá trị cốt lõi: {char.core_value}")
            if char.fear:
                parts.append(f"  Nỗi sợ: {char.fear}")
            if char.weakness:
                parts.append(f"  Điểm yếu: {char.weakness}")
            if char.catchphrase:
                parts.append(f"  Câu cửa miệng: {char.catchphrase}")
            if char.relationships:
                rel_lines = [f"    + {r.target_name} ({r.type}): {r.dynamic}" for r in char.relationships]
                parts.append("  Quan hệ:\n" + "\n".join(rel_lines))
            lines.append("\n".join(parts))
        return "\n\n".join(lines)

