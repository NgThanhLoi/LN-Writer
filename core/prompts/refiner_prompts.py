CONTENT_REFINER_PROMPT = """Bạn là editor chuyên nghiệp cho light novel tiếng Việt.

Nhiệm vụ: **nâng cao chất lượng văn xuôi** của chương sau mà KHÔNG thay đổi plot, nhân vật, hay sự kiện.

{genre_refinement_hints}

**Chương cần cải thiện:**
Chương {chapter_number}: {chapter_title}

---
{draft_content}
---

**Nguyên tắc cải thiện:**
- Giữ nguyên 100% plot, nhân vật, sự kiện, dialogue, cliffhanger
- Bớt câu lặp cấu trúc liên tiếp (tránh 3+ câu cùng bắt đầu bằng chủ ngữ giống nhau)
- Thay "kể cảm xúc" bằng "diễn tả qua hành động/giác quan" (show don't tell)
- Câu ngắn khi căng thẳng, câu dài khi trầm tư — nhịp điệu phù hợp tình huống
- Trả về TOÀN BỘ chương đã refined — không tóm tắt, không bỏ đoạn nào
- Độ dài xấp xỉ bản gốc (±10%)

Chỉ trả về nội dung chương, không thêm ghi chú hay giải thích.
"""

# ── Genre-specific refinement hints ──────────────────────────────────────────

_ISEKAI_HINTS = """**Phong cách Isekai — hướng dẫn refinement:**
- Giữ năng lượng hào hứng, tươi mới — đây là điểm mạnh nhất của thể loại
- Nội tâm nhân vật: cụ thể, pha chút tự trào khi so sánh với thế giới cũ
- Wonder: mô tả thế giới mới qua phản ứng cảm xúc thật, không liệt kê khô khan
- Hội thoại: sắc nét, bộc lộ tính cách — tránh thoại chỉ để giải thích thế giới"""

_TUTIEN_HINTS = """**Phong cách Tu tiên — hướng dẫn refinement:**
- Giữ sự trang trọng, hào sảng — tránh ngôn ngữ quá hiện đại
- Khoảnh khắc đột phá/sinh tử: nội tâm sâu, cảm giác thân xác rõ ràng (linh khí chạy qua kinh mạch, đau buốt, ấm áp)
- Thuật ngữ tu tiên: dùng nhất quán, không giải thích quá nhiều
- Chiến đấu: nhịp câu ngắn dần khi đỉnh điểm, xen lẫn nội tâm chớp nhoáng"""

_XUYENKHONG_HINTS = """**Phong cách Xuyên không — hướng dẫn refinement:**
- Tương phản hiện đại vs cổ đại: khai thác tối đa để tạo hài hước kín đáo và nội tâm thú vị
- Nội tâm: nhân vật so sánh với kiến thức hiện đại — cụ thể, tình huống thực, không chung chung
- Ngôn ngữ cổ phong: nhân vật phụ nói cổ, nhân vật chính nghĩ theo kiểu hiện đại — tương phản rõ
- Cung đình/lễ nghi: mô tả đủ chi tiết để tạo không khí, không sa vào liệt kê"""

_ROMANCE_HINTS = """**Phong cách Romance — hướng dẫn refinement:**
- Ngôn ngữ cảm xúc: tinh tế, qua chi tiết nhỏ (ánh mắt tránh né, bàn tay hơi run, tiếng tim đập)
- Subtext: ý nghĩa thật ẩn dưới lời nói — đừng giải thích hết cho độc giả
- Câu ngắn khi cảm xúc cao trào: nhịp tim nhanh = câu ngắn
- Khoảnh khắc nhỏ > sự kiện lớn: một cái chạm tay đúng lúc mạnh hơn mười lời thổ lộ"""

_KINHDI_HINTS = """**Phong cách Kinh dị — hướng dẫn refinement:**
- Pacing chậm có chủ đích: đừng rush đến sợ hãi — dẫn dắt bằng sự bất an ngấm dần
- Sensory horror: âm thanh (tiếng gõ nhịp đều trong tường), mùi (tanh ngọt như máu), lạnh bất thường
- Tránh kể trực tiếp "cô ấy sợ hãi" — mô tả: "tay cô không còn vâng lời nữa"
- Chi tiết đời thường bị làm cho kỳ lạ: hiệu quả hơn cái ghê tởm thuần túy
- Câu đứt đoạn khi hoảng loạn — dấu "..." có chủ đích"""

_HANHDONG_HINTS = """**Phong cách Hành động (Shonen) — hướng dẫn refinement:**
- Combat: câu siêu ngắn khi đỉnh điểm. "Hắn lao tới. Một cú đấm. Aria né. Phản đòn."
- Action verbs mạnh: "lao", "xé", "nghiến", "bùng cháy" > "di chuyển", "tấn công", "cảm thấy"
- Cinematic: mô tả góc nhìn (tầm mắt thấp, cận cảnh vết thương) như quay phim
- Ý chí: nội tâm ngắn gọn, bùng lên đúng lúc — không triết lý dài dòng
- Aftermath: để nhân vật thở — xen khoảng lặng sau combat tạo contrast"""


GENRE_REFINEMENT_HINTS = {
    "isekai":      _ISEKAI_HINTS,
    "tu_tien":     _TUTIEN_HINTS,
    "xuyen_khong": _XUYENKHONG_HINTS,
    "romance":     _ROMANCE_HINTS,
    "kinh_di":     _KINHDI_HINTS,
    "hanh_dong":   _HANHDONG_HINTS,
}
