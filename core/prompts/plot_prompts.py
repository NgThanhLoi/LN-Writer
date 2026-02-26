PLOT_NAVIGATOR_PROMPT = """Bạn là một nhà văn light novel Việt Nam chuyên nghiệp.

Dựa trên ý tưởng sau, hãy tạo ra một kế hoạch cốt truyện chi tiết cho {num_chapters} chương đầu tiên của bộ light novel **thể loại {genre_name}**.

{genre_hints}

**Ý tưởng của tác giả:**
{user_prompt}

**Yêu cầu output (JSON):**
Trả về JSON theo đúng format sau, không có text thêm vào trước hoặc sau:

{{
  "title": "Tựa đề light novel",
  "premise": "Tóm tắt tiền đề câu chuyện trong 2-3 câu",
  "world_summary": "Mô tả thế giới trong 3-4 câu: bối cảnh, magic system, xã hội",
  "chapters": [
    {{
      "number": 1,
      "title": "Tựa đề chương 1",
      "pov_character": "Tên nhân vật POV",
      "opening_hook": "Câu/đoạn mở đầu gây tò mò — 1-2 câu mô tả hook",
      "ending_cliffhanger": "Cliffhanger kết chương — 1-2 câu mô tả",
      "outline_beats": [
        "Beat 1: ...",
        "Beat 2: ...",
        "Beat 3: ...",
        "Beat 4: ..."
      ]
    }}
  ]
}}

**Lưu ý:**
- Mỗi chương cần có ít nhất 4 story beats
- Opening hook phải gây tò mò ngay lập tức
- Ending cliffhanger phải khiến độc giả muốn đọc tiếp
- Cốt truyện cần có nhịp điệu tăng dần, chương sau căng thẳng hơn chương trước
"""


# ── Genre style guides (dùng trong DraftMaster) ─────────────────────────────

ISEKAI_GENRE_STYLE = """**Thể loại: Isekai**
- Giọng văn: Năng động, hào hứng, đôi khi hài hước
- Từ vựng: Đời thường pha lẫn thuật ngữ game/fantasy (level, skill, boss, quest)
- Câu trung bình: 12-15 từ
- Hội thoại: ~50% nội dung, đối thoại sắc bén và thể hiện tính cách
- Nội tâm nhân vật: Thường xuyên, nhất là khi khám phá thế giới mới
- Mô tả: Vừa đủ, tập trung vào những gì bất ngờ/khác lạ so với thế giới hiện đại"""

TUTION_GENRE_STYLE = """**Thể loại: Tu tiên (Tiên Hiệp)**
- Giọng văn: Trang trọng, hào sảng, pha chút thâm thúy
- Từ vựng: Thuật ngữ tu tiên (linh khí, đan dược, cảnh giới, tu vi, đột phá, thiên tài)
- Câu trung bình: 15-20 từ, câu văn dài hơn khi mô tả cảnh giới và chiến đấu
- Hội thoại: ~35% nội dung, lời thoại ngắn gọn súc tích và đầy ẩn ý
- Nội tâm nhân vật: Sâu sắc, nhất là khi đột phá hoặc đối mặt sinh tử
- Mô tả: Chi tiết về cảnh giới tu luyện, chiến đấu, thiên địa linh vật"""

XUYEN_KHONG_GENRE_STYLE = """**Thể loại: Xuyên không (Cổ đại / Lịch sử)**
- Giọng văn: Tinh tế, pha chút hài hước kín đáo của người hiện đại bị ném vào cổ đại
- Từ vựng: Cổ phong pha lẫn suy nghĩ hiện đại (tương phản tạo hiệu ứng)
- Câu trung bình: 13-17 từ
- Hội thoại: ~45% nội dung, lời thoại phân biệt rõ giai tầng xã hội
- Nội tâm nhân vật: Rất thường xuyên — nhân vật luôn so sánh với kiến thức hiện đại
- Mô tả: Phong phú về cung đình, lễ nghi, trang phục, ẩm thực thời cổ đại"""

ROMANCE_GENRE_STYLE = """**Thể loại: Romance (Tình cảm đương đại)**
- Giọng văn: Nhẹ nhàng, tinh tế, cảm xúc chân thực
- Từ vựng: Đời thường, gần gũi, đặc biệt chú ý ngôn ngữ cảm xúc
- Câu trung bình: 10-14 từ, ưu tiên câu ngắn khi cảm xúc cao trào
- Hội thoại: ~55% nội dung, mỗi câu thoại đẩy cảm xúc/tension lên thêm
- Nội tâm nhân vật: Rất nhiều, đặc biệt xung quanh cảm xúc và hiểu lầm
- Mô tả: Tập trung vào chi tiết cảm xúc và khoảnh khắc nhỏ có ý nghĩa lớn"""


GENRE_STYLES = {
    "isekai":     ISEKAI_GENRE_STYLE,
    "tu_tien":    TUTION_GENRE_STYLE,
    "xuyen_khong": XUYEN_KHONG_GENRE_STYLE,
    "romance":    ROMANCE_GENRE_STYLE,
}


# ── Genre-specific plot hints (dùng trong PlotNavigator) ─────────────────────

_ISEKAI_PLOT_HINTS = """**Lưu ý thể loại Isekai:**
- Nhân vật chính đến từ thế giới hiện đại, bị isekai vào thế giới fantasy/game
- Cần có: moment khám phá kỹ năng/cheat, encounter đầu tiên với cư dân thế giới mới
- Tropes hay dùng: system thông báo, level up, party, guild, dungeon
- Chapter 1 thường: cảnh isekai + phát hiện cheat ability"""

_TUTION_PLOT_HINTS = """**Lưu ý thể loại Tu tiên:**
- Nhân vật chính bước vào con đường tu tiên, thường xuất phát điểm thấp nhưng có cơ duyên
- Cần có: hệ thống cảnh giới rõ ràng (Luyện Khí → Trúc Cơ → Kim Đan...), môn phái hoặc gia tộc
- Tropes hay dùng: thiên tài bị hiểu lầm, cơ duyên trời rơi, tu vi đột phá, thù hận gia tộc
- Chapter 1 thường: giới thiệu xuất thân + cơ duyên đầu tiên mở đường tu tiên"""

_XUYEN_KHONG_PLOT_HINTS = """**Lưu ý thể loại Xuyên không:**
- Nhân vật chính từ hiện đại xuyên vào cổ đại (thường là cung đình, gia tộc quyền quý)
- Cần có: shock ban đầu khi nhận ra mình xuyên không, tận dụng kiến thức hiện đại
- Tropes hay dùng: thay thân phận nhân vật cổ đại, tránh kiếp nạn đã biết, thay đổi số phận
- Chapter 1 thường: tỉnh dậy trong thân xác mới + nhận ra tình huống nguy hiểm cần giải quyết"""

_ROMANCE_PLOT_HINTS = """**Lưu ý thể loại Romance:**
- Xây dựng tension cảm xúc dần dần, không rush vào tình cảm ngay
- Cần có: lý do hai nhân vật chính tiếp xúc, misunderstanding/obstacle đầu tiên
- Tropes hay dùng: enemies to lovers, second chance, forced proximity, slow burn
- Chapter 1 thường: gặp gỡ định mệnh có kèm theo conflict hoặc ấn tượng sai lầm"""


GENRE_PLOT_HINTS = {
    "isekai":      _ISEKAI_PLOT_HINTS,
    "tu_tien":     _TUTION_PLOT_HINTS,
    "xuyen_khong": _XUYEN_KHONG_PLOT_HINTS,
    "romance":     _ROMANCE_PLOT_HINTS,
}

PLOT_CONTINUATION_PROMPT = """Bạn là nhà văn light novel Việt Nam chuyên nghiệp.

Câu chuyện **{title}** đã có {existing_count} chương. Bạn cần tạo outline cho {num_new_chapters} chương tiếp theo (chương {start_chapter} đến {end_chapter}).

**Thể loại: {genre_name}**
{genre_hints}

**Tiền đề:**
{premise}

**Tóm tắt những gì đã xảy ra:**
{existing_summary}

**Cliffhanger chương cuối ({existing_count}):**
{last_cliffhanger}

**Yêu cầu output (JSON):**
Trả về JSON theo đúng format sau, không có text thêm vào trước hoặc sau:

{{
  "chapters": [
    {{
      "number": {start_chapter},
      "title": "Tựa đề chương",
      "pov_character": "Tên nhân vật POV",
      "opening_hook": "Tiếp nối trực tiếp cliffhanger chương trước — 1-2 câu",
      "ending_cliffhanger": "Cliffhanger mới — 1-2 câu",
      "outline_beats": ["Beat 1", "Beat 2", "Beat 3", "Beat 4"]
    }}
  ]
}}

**Lưu ý:**
- Chương {start_chapter} phải tiếp nối TRỰC TIẾP cliffhanger chương {existing_count}
- Narrative arc phải có climax ở chương {end_chapter}
- Tăng dần độ căng thẳng qua các chương
- Mỗi chương cần ít nhất 4 story beats
"""


GENRE_DISPLAY_NAMES = {
    "isekai":      "Isekai",
    "tu_tien":     "Tu tiên",
    "xuyen_khong": "Xuyên không",
    "romance":     "Romance",
}
