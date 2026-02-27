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
      "current_state": "Trạng thái khi xuất hiện",
      "core_value": "Điều nhân vật không bao giờ thỏa hiệp, dù phải trả giá đắt",
      "fear": "Nỗi sợ lớn nhất — cụ thể, không chung chung",
      "weakness": "Giới hạn/điểm yếu tạo ra drama và tension",
      "catchphrase": "1-2 câu nói/biểu hiện đặc trưng nhất vẫn hay lặp lại",
      "relationships": [
        {{
          "target_name": "Tên nhân vật hiện có",
          "type": "rival",
          "dynamic": "Mô tả 1 câu về dynamic cụ thể giữa hai người"
        }}
      ]
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
      "current_state": "Trạng thái hiện tại ở đầu câu chuyện",
      "core_value": "Điều nhân vật không bao giờ thỏa hiệp, dù phải trả giá đắt — đây là la bàn đạo đức của họ",
      "fear": "Nỗi sợ lớn nhất, cụ thể và sâu sắc — không phải 'sợ chết' chung chung mà là 'sợ mất đi người duy nhất tin mình'",
      "weakness": "Giới hạn hoặc điểm yếu tạo ra tension và drama — ví dụ: kiêu ngạo che giấu sự mất tự tin, không thể từ chối người nhờ vả",
      "catchphrase": "1-2 câu nói hoặc cách biểu đạt đặc trưng mà nhân vật hay lặp lại khi căng thẳng/vui/buồn",
      "relationships": [
        {{
          "target_name": "Tên nhân vật khác trong danh sách",
          "type": "friend|rival|mentor|enemy|romantic",
          "dynamic": "Mô tả 1 câu về dynamic cụ thể: ai có quyền lực hơn, điểm căng thẳng là gì, cảm xúc thật bên dưới"
        }}
      ]
    }}
  ]
}}

**Yêu cầu:**
- Tạo 2-4 nhân vật: 1 protagonist, 1-2 supporting, tùy chọn 1 antagonist
- Mỗi nhân vật phải có speech_pattern RÕ RÀNG và KHÁC BIỆT với nhau
- Backstory phải liên quan trực tiếp đến plot
- Personality traits phải thể hiện được qua hành động và lời thoại
- fear phải là nguồn conflict nội tâm cụ thể, không chung chung
- relationships phải có đủ cho tất cả cặp nhân vật quan trọng (protagonist ↔ các character khác)
"""
