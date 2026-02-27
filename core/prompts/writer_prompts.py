DRAFT_MASTER_PROMPT = """Bạn là nhà văn light novel Việt Nam chuyên nghiệp, đang viết chương {chapter_number} của bộ truyện "{title}".

{genre_style}

**Thông tin cốt truyện:**
{premise}

**Thế giới:**
{world_summary}

**Nhân vật xuất hiện trong chương này:**
{characters_info}

**Kế hoạch chương {chapter_number}: {chapter_title}**
- POV: {pov_character}
- Mở đầu: {opening_hook}
- Kết chương: {ending_cliffhanger}
- Story beats:
{outline_beats}

{previous_context}

**Yêu cầu viết — BẮT BUỘC:**
- Viết TỐI THIỂU {target_words} từ. Nếu chưa đủ, mở rộng scene, thêm inner monologue, chi tiết hóa dialogue. KHÔNG được kết thúc sớm.
- Bắt đầu NGAY bằng nội dung, không có tiêu đề chương
- Thể hiện rõ giọng nói đặc trưng của từng nhân vật khi họ nói chuyện (dùng catchphrase nếu phù hợp)
- Tạo inner monologue dựa trên core_value và fear của nhân vật POV
- Tận dụng weakness của nhân vật để tạo tension và drama
- Thể hiện dynamic relationship giữa các nhân vật qua cách họ tương tác
- Mở đầu phải bắt đúng hook đã plan: {opening_hook}

⚠️ CLIFFHANGER — QUAN TRỌNG NHẤT:
Câu CUỐI CÙNG của chương phải là cliffhanger này (hoặc diễn đạt lại giữ nguyên ý):
"{ending_cliffhanger}"
KHÔNG được kết thúc bằng suy nghĩ nội tâm bình thường hay mô tả cảnh vật.
Phải kết thúc bằng hành động bất ngờ, câu thoại gây sốc, hoặc revelation đột ngột.

- Văn phong nhất quán, câu văn tự nhiên tiếng Việt

Bắt đầu viết:"""


PREVIOUS_CONTEXT_TEMPLATE = """**Ngữ cảnh từ chương trước (500 từ cuối):**
{tail_content}

**Tóm tắt những gì đã xảy ra:**
{chapter_summaries}"""


CHAPTER_SUMMARY_PROMPT = """Tóm tắt chương sau trong 150 từ, tập trung vào:
- Các sự kiện chính đã xảy ra
- Trạng thái hiện tại của nhân vật
- Plot threads đang active
- Kết thúc chương (cliffhanger nếu có)

Chương {chapter_number} — {chapter_title}:
{chapter_content}

Tóm tắt (150 từ):"""
