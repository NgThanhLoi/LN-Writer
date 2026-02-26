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
      "issue_type": "speech_pattern | personality | name_error | continuity",
      "description": "Mô tả vấn đề cụ thể",
      "quote": "Trích dẫn đoạn văn có vấn đề"
    }}
  ],
  "summary": "Tóm tắt kết quả kiểm tra trong 1-2 câu"
}}

**Quy tắc:**
- `passed: true` nếu không có issues nghiêm trọng (speech_pattern, name_error)
- `passed: false` nếu có ít nhất 1 issue loại speech_pattern hoặc name_error
- Liệt kê TẤT CẢ issues tìm thấy, kể cả khi passed=true
"""
