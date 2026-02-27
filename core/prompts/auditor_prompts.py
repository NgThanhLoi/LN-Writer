AUDITOR_PROMPT = """Bạn là editor kiểm tra tính nhất quán nhân vật trong light novel.

**Profiles nhân vật (chuẩn):**
{character_profiles}

**Nội dung chương {chapter_number} cần kiểm tra:**
{chapter_content}

Hãy kiểm tra xem nhân vật trong chương có nhất quán với profiles không.

**Yêu cầu output (JSON):**
Trả về JSON theo đúng format sau, không có text thêm vào trước hoặc sau:

{{
  "passed": true,
  "issues": [
    {{
      "character": "Tên nhân vật",
      "issue_type": "speech_pattern | personality | name_error | continuity | core_value | catchphrase",
      "description": "Mô tả vấn đề cụ thể",
      "quote": "Trích dẫn đoạn văn có vấn đề"
    }}
  ],
  "summary": "Tóm tắt kết quả kiểm tra trong 1-2 câu"
}}

**Quy tắc:**
- `passed: true` nếu không có issues nghiêm trọng (speech_pattern, name_error, core_value)
- `passed: false` nếu có ít nhất 1 issue loại speech_pattern, name_error, hoặc core_value
- Liệt kê TẤT CẢ issues tìm thấy, kể cả khi passed=true
- Kiểm tra thêm: nhân vật có hành động trái với `Giá trị cốt lõi` không? Câu cửa miệng có được dùng tự nhiên không?
"""
