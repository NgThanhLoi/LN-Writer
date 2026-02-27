import json
import logging
import uuid
from core.ai_adapter import build_adapter, parse_json_response
from core.models import Chapter, CharacterProfile, CharacterRelationship, StoryBlueprint

logger = logging.getLogger(__name__)

BLUEPRINT_EXTRACTOR_PROMPT = """Bạn là chuyên gia phân tích light novel tiếng Việt.

Hãy đọc nội dung truyện sau và trích xuất thông tin để tạo blueprint cho phần tiếp theo.

**Nội dung truyện:**
{source_content}

**Yêu cầu output (JSON):**
Trả về JSON theo đúng format sau, không có text thêm vào trước hoặc sau:

{{
  "title": "Tựa đề truyện (nếu không rõ thì đặt tên phù hợp)",
  "premise": "Tóm tắt tiền đề câu chuyện trong 2-3 câu",
  "world_summary": "Bối cảnh thế giới: thời đại, địa điểm, hệ thống ma pháp/quyền lực nếu có (3-4 câu)",
  "detected_genre": "isekai | tu_tien | xuyen_khong | romance | kinh_di | hanh_dong",
  "last_cliffhanger": "Tóm tắt 1-2 câu: câu chuyện đang dở ở đâu, tension hiện tại là gì",
  "chapter_count": 0,
  "characters": [
    {{
      "id": "char_001",
      "name": "Tên nhân vật",
      "role": "protagonist | antagonist | supporting",
      "personality_traits": ["trait1", "trait2", "trait3"],
      "speech_pattern": "Cách nói chuyện đặc trưng",
      "backstory": "Quá khứ ngắn gọn",
      "goals": ["mục tiêu chính"],
      "current_state": "Trạng thái hiện tại cuối truyện",
      "core_value": "Điều nhân vật không bao giờ thỏa hiệp",
      "fear": "Nỗi sợ lớn nhất",
      "weakness": "Điểm yếu",
      "catchphrase": "Câu nói đặc trưng nếu có",
      "relationships": []
    }}
  ],
  "chapter_summaries": [
    {{
      "number": 1,
      "title": "Tựa đề chương nếu có",
      "summary": "Tóm tắt 2-3 câu những gì xảy ra"
    }}
  ]
}}

**Lưu ý:**
- Trích xuất nhân vật chính và các nhân vật phụ quan trọng (tối đa 6 nhân vật)
- Nếu không xác định được chapter boundaries, tạo 1 summary cho toàn bộ nội dung
- detected_genre: chọn thể loại phù hợp nhất với nội dung
- last_cliffhanger: QUAN TRỌNG — đây là điểm nối để viết tiếp
"""


class BlueprintExtractorAgent:
    """Extract a StoryBlueprint from existing novel content (Mode A of /import)."""

    def run(self, source_content: str, num_new_chapters: int,
            words_per_chapter: int, style_config: dict | None = None) -> StoryBlueprint:
        logger.info("Extracting blueprint from source content...")

        # Truncate if too long — keep head + tail to preserve context
        if len(source_content) > 200_000:
            half = 100_000
            source_content = (
                source_content[:half]
                + "\n\n[...nội dung giữa bị cắt bớt để fit context...]\n\n"
                + source_content[-half:]
            )

        prompt = BLUEPRINT_EXTRACTOR_PROMPT.format(source_content=source_content)
        ai = build_adapter("plot_navigator")  # use pro model for extraction quality
        response = ai.generate(prompt, max_tokens=4096)

        try:
            data = parse_json_response(response)
        except ValueError as e:
            raise ValueError(f"BlueprintExtractor: could not parse AI response — {e}") from e

        # Build chapter objects for the NEW chapters to write
        # (not the existing ones — those are summarized)
        last_cliffhanger = data.get("last_cliffhanger", "")
        existing_count = data.get("chapter_count", len(data.get("chapter_summaries", [])))
        start_num = existing_count + 1

        # Create placeholder Chapter objects for new chapters to be written
        # PlotNavigator will fill these in properly during continuation
        # Here we just need empty stubs that the blueprint holds
        new_chapters = [
            Chapter(
                id=f"import_ch_{i:03d}",
                number=start_num + i - 1,
                title=f"Chương {start_num + i - 1}",
                opening_hook=last_cliffhanger if i == 1 else "",
                ending_cliffhanger="",
                pov_character="",
                outline_beats=[],
            )
            for i in range(1, num_new_chapters + 1)
        ]

        # Build characters
        characters = []
        for i, c in enumerate(data.get("characters", []), 1):
            rels = [CharacterRelationship(**r) for r in c.pop("relationships", [])]
            c.setdefault("id", f"char_{i:03d}")
            c.setdefault("personality_traits", [])
            c.setdefault("goals", [])
            c.setdefault("speech_pattern", "")
            c.setdefault("backstory", "")
            c.setdefault("current_state", "")
            c.setdefault("core_value", "")
            c.setdefault("fear", "")
            c.setdefault("weakness", "")
            c.setdefault("catchphrase", "")
            characters.append(CharacterProfile(**c, relationships=rels))

        # Build chapter_summaries dict for context
        chapter_summaries: dict[int, str] = {}
        for cs in data.get("chapter_summaries", []):
            chapter_summaries[cs["number"]] = cs.get("summary", "")

        blueprint = StoryBlueprint(
            title=data.get("title", "Untitled"),
            premise=data.get("premise", ""),
            genre=data.get("detected_genre", "isekai"),
            target_chapters=num_new_chapters,
            words_per_chapter=words_per_chapter,
            world_summary=data.get("world_summary", ""),
            chapters=new_chapters,
            characters=characters,
            style_config=style_config,
        )

        logger.info(
            f"Extracted: '{blueprint.title}', genre={blueprint.genre}, "
            f"{len(characters)} chars, {len(chapter_summaries)} summaries, "
            f"continuation from ch{existing_count + 1}"
        )

        return blueprint, chapter_summaries, existing_count
