import json
from core.ai_adapter import build_adapter, parse_json_response
from core.models import Chapter, CharacterProfile
from core.prompts.auditor_prompts import AUDITOR_PROMPT


class FinalAuditorAgent:
    def run(self, chapter: Chapter, characters: list[CharacterProfile]) -> dict:
        ai = build_adapter("final_auditor")
        print(f"  [FinalAuditor] Auditing chapter {chapter.number}...")
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
            print("  [FinalAuditor] Warning: could not parse audit response — treating as FAILED.")
            result = {"passed": False, "issues": [], "summary": "Auditor parse error — chapter will be regenerated."}

        passed = result.get("passed", False)
        issues = result.get("issues", [])
        summary = result.get("summary", "")

        if passed:
            print(f"  [FinalAuditor] PASSED. {summary}")
        else:
            print(f"  [FinalAuditor] FAILED. {len(issues)} issue(s) found.")
            for issue in issues:
                print(f"    - [{issue.get('issue_type')}] {issue.get('character')}: {issue.get('description')}")

        return result

    def _format_profiles(self, characters: list[CharacterProfile]) -> str:
        lines = []
        for char in characters:
            traits = ", ".join(char.personality_traits)
            lines.append(
                f"**{char.name}** ({char.role})\n"
                f"  Tính cách: {traits}\n"
                f"  Cách nói: {char.speech_pattern}\n"
                f"  Backstory: {char.backstory}"
            )
        return "\n\n".join(lines)

