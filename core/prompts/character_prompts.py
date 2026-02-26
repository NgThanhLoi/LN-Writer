CHARACTER_ADDITIONS_PROMPT = """Bạn là chuyên gia xây dựng nhân vật cho light novel Việt Nam.

**Nhân vật hiện có:**
{existing_characters}

**Outline các chương mới:**
{new_chapters_outline}

Đề xuất 0-3 nhân vật MỚI cần thêm cho phần tiếp theo. Không tạo lại nhân vật đã có.
Nếu nhân vật hiện tại đã đủ, trả về mảng rỗng.

**Yêu cầu output (JSON):**
Trả về JSON theo đúng format sau, không có text thêm vào trước hoặc sau:

{{
  "characters": [
    {{
      "id": "char_new_001",
      "name": "Tên nhân vật mới",
      "role": "supporting",
      "personality_traits": ["trait1", "trait2"],
      "speech_pattern": "Mô tả cách nói đặc trưng",
      "backstory": "Tiểu sử trong 1-2 câu",
      "goals": ["Mục tiêu"],
      "current_state": "Trạng thái khi xuất hiện"
    }}
  ]
}}
"""


CHARACTER_SOUL_PROMPT = """Bạn là chuyên gia xây dựng nhân vật cho light novel Việt Nam thể loại isekai.

**Cốt truyện:**
{premise}

**Thế giới:**
{world_summary}

**Kế hoạch {num_chapters} chương:**
{chapters_outline}

Hãy tạo ra các nhân vật chính cho câu chuyện này.

**Yêu cầu output (JSON):**
Trả về JSON theo đúng format sau, không có text thêm vào trước hoặc sau:

{{
  "characters": [
    {{
      "id": "char_001",
      "name": "Tên nhân vật",
      "role": "protagonist",
      "personality_traits": ["trait1", "trait2", "trait3"],
      "speech_pattern": "Mô tả cách nói đặc trưng: ví dụ dùng từ gì, câu ngắn/dài, hay dùng từ lóng không, v.v.",
      "backstory": "Tiểu sử trong 2-3 câu",
      "goals": ["Mục tiêu ngắn hạn", "Mục tiêu dài hạn"],
      "current_state": "Trạng thái hiện tại ở đầu câu chuyện"
    }}
  ]
}}

**Yêu cầu:**
- Tạo 2-4 nhân vật: 1 protagonist, 1-2 supporting, tùy chọn 1 antagonist
- Mỗi nhân vật phải có speech_pattern RÕ RÀNG và KHÁC BIỆT với nhau
- Backstory phải liên quan trực tiếp đến plot
- Personality traits phải thể hiện được qua hành động và lời thoại
"""
