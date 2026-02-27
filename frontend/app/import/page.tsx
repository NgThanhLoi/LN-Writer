"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { API } from "../lib/constants";

type Mode = "content" | "description";
type Tone = "light" | "neutral" | "tense";
type DialogueRatio = "low" | "medium" | "high";

const GENRES = [
  { value: "isekai", label: "Isekai" },
  { value: "tu_tien", label: "Tu tiên" },
  { value: "xuyen_khong", label: "Xuyên không" },
  { value: "romance", label: "Romance" },
  { value: "kinh_di", label: "Kinh dị" },
  { value: "hanh_dong", label: "Hành động" },
] as const;

export default function ImportPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("content");
  const [sourceContent, setSourceContent] = useState("");
  const [description, setDescription] = useState("");
  const [chapters, setChapters] = useState(3);
  const [words, setWords] = useState(4500);
  const [genre, setGenre] = useState("isekai");
  const [tone, setTone] = useState<Tone>("neutral");
  const [dialogueRatio, setDialogueRatio] = useState<DialogueRatio>("medium");
  const [customNote, setCustomNote] = useState("");
  const [qualityMode, setQualityMode] = useState(false);
  const [showStyle, setShowStyle] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const value = mode === "content" ? sourceContent : description;
    if (!value.trim()) return;
    setLoading(true);
    setError("");

    try {
      const res = await fetch(`${API}/novels/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode,
          source_content: mode === "content" ? sourceContent : "",
          description: mode === "description" ? description : "",
          num_chapters: chapters,
          words_per_chapter: words,
          genre,
          style_config: {
            tone,
            dialogue_ratio: dialogueRatio,
            custom_note: customNote,
            quality_mode: qualityMode,
          },
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const { id } = await res.json();
      router.push(`/write/${id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setLoading(false);
    }
  }

  const charCount = mode === "content" ? sourceContent.length : description.length;
  const wordCount = mode === "content"
    ? sourceContent.split(/\s+/).filter(Boolean).length
    : 0;

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6 py-16">
      {/* Nav */}
      <div className="absolute top-6 left-6">
        <Link
          href="/"
          className="text-sm font-semibold transition-colors"
          style={{ color: "var(--muted)" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--amber)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--muted)")}
        >
          ← Trang chủ
        </Link>
      </div>
      <div className="absolute top-6 right-6">
        <Link
          href="/novels"
          className="text-sm font-semibold uppercase tracking-widest transition-colors"
          style={{ color: "var(--muted)" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--amber)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--muted)")}
        >
          Thư viện →
        </Link>
      </div>

      {/* Header */}
      <div className="fade-up text-center mb-12">
        <div className="flex items-center justify-center gap-3 mb-4">
          <span className="amber-rule" />
          <span className="text-xs uppercase tracking-[0.25em] font-semibold" style={{ color: "var(--amber)" }}>
            Tiếp nối truyện
          </span>
          <span className="amber-rule" />
        </div>
        <h1
          className="text-4xl md:text-5xl font-bold leading-tight mb-3"
          style={{ fontFamily: "var(--font-playfair)", color: "var(--heading)" }}
        >
          Viết tiếp từ đây
        </h1>
        <p className="text-base max-w-md mx-auto" style={{ color: "var(--subtle)" }}>
          Paste nội dung truyện gốc hoặc mô tả đại ý — AI sẽ viết tiếp.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="fade-up w-full max-w-2xl" style={{ animationDelay: "0.1s", opacity: 0 }}>

        {/* Mode selector */}
        <div className="mb-6">
          <div className="grid grid-cols-2 gap-2">
            {([
              { value: "content", label: "📄 Có nội dung gốc", desc: "Paste chương, đoạn văn — AI phân tích và viết tiếp" },
              { value: "description", label: "💭 Chỉ nhớ đại ý", desc: "Mô tả truyện — AI tự dựng phần tiếp theo" },
            ] as const).map(({ value, label, desc }) => (
              <button
                key={value}
                type="button"
                onClick={() => setMode(value)}
                className="py-3 px-4 rounded-sm text-sm font-semibold transition-all text-left"
                style={{
                  background: mode === value ? "var(--amber)" : "var(--surface)",
                  color: mode === value ? "var(--ink)" : "var(--subtle)",
                  border: `1px solid ${mode === value ? "var(--amber)" : "var(--border)"}`,
                }}
              >
                <div>{label}</div>
                <div className="text-xs font-normal mt-0.5 opacity-75">{desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Content input */}
        {mode === "content" ? (
          <div className="relative mb-6">
            <textarea
              value={sourceContent}
              onChange={(e) => setSourceContent(e.target.value)}
              placeholder="Paste nội dung truyện vào đây — có thể là 1 chương hay toàn bộ…"
              rows={10}
              required
              className="w-full rounded-sm resize-none px-5 py-4 text-base leading-relaxed focus:outline-none transition-all"
              style={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                color: "var(--body)",
                fontFamily: "var(--font-inter)",
              }}
              onFocus={(e) => {
                e.target.style.borderColor = "var(--amber)";
                e.target.style.boxShadow = "0 0 0 2px var(--amber-glow)";
              }}
              onBlur={(e) => {
                e.target.style.borderColor = "var(--border)";
                e.target.style.boxShadow = "none";
              }}
            />
            <div className="absolute bottom-3 right-4 text-xs" style={{ color: "var(--muted)" }}>
              {charCount.toLocaleString()} ký tự · ~{wordCount.toLocaleString()} từ
            </div>
          </div>
        ) : (
          <div className="relative mb-6">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Vd: Truyện về một thám tử bị oan, vừa trốn thoát khỏi nhà tù và đang truy tìm kẻ thật sự. Câu chuyện dừng lại khi hắn phát hiện manh mối tại căn nhà bỏ hoang…"
              rows={6}
              required
              className="w-full rounded-sm resize-none px-5 py-4 text-base leading-relaxed focus:outline-none transition-all"
              style={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                color: "var(--body)",
                fontFamily: "var(--font-inter)",
              }}
              onFocus={(e) => {
                e.target.style.borderColor = "var(--amber)";
                e.target.style.boxShadow = "0 0 0 2px var(--amber-glow)";
              }}
              onBlur={(e) => {
                e.target.style.borderColor = "var(--border)";
                e.target.style.boxShadow = "none";
              }}
            />
            <div className="absolute bottom-3 right-4 text-xs" style={{ color: "var(--muted)" }}>
              {charCount} ký tự
            </div>
          </div>
        )}

        {/* Genre — only shown for Mode B (Mode A auto-detects) */}
        {mode === "description" && (
          <div className="mb-6">
            <span className="text-xs uppercase tracking-widest font-semibold mb-2 block" style={{ color: "var(--muted)" }}>
              Thể loại
            </span>
            <div className="grid grid-cols-3 gap-2">
              {GENRES.map(({ value, label }) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setGenre(value)}
                  className="py-2 rounded-sm text-sm font-semibold transition-all"
                  style={{
                    background: genre === value ? "var(--amber)" : "var(--surface)",
                    color: genre === value ? "var(--ink)" : "var(--subtle)",
                    border: `1px solid ${genre === value ? "var(--amber)" : "var(--border)"}`,
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Options row */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          <label className="flex flex-col gap-2">
            <span className="text-xs uppercase tracking-widest font-semibold" style={{ color: "var(--muted)" }}>
              Số chương viết tiếp
            </span>
            <div className="flex gap-2">
              {[3, 5, 10].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setChapters(n)}
                  className="flex-1 py-2 rounded-sm text-sm font-semibold transition-all"
                  style={{
                    background: chapters === n ? "var(--amber)" : "var(--surface)",
                    color: chapters === n ? "var(--ink)" : "var(--subtle)",
                    border: `1px solid ${chapters === n ? "var(--amber)" : "var(--border)"}`,
                  }}
                >
                  {n}
                </button>
              ))}
            </div>
          </label>
          <label className="flex flex-col gap-2">
            <span className="text-xs uppercase tracking-widest font-semibold" style={{ color: "var(--muted)" }}>
              Từ / chương
            </span>
            <div className="flex gap-2">
              {[3000, 4500, 6000].map((w) => (
                <button
                  key={w}
                  type="button"
                  onClick={() => setWords(w)}
                  className="flex-1 py-2 rounded-sm text-sm font-semibold transition-all"
                  style={{
                    background: words === w ? "var(--amber)" : "var(--surface)",
                    color: words === w ? "var(--ink)" : "var(--subtle)",
                    border: `1px solid ${words === w ? "var(--amber)" : "var(--border)"}`,
                  }}
                >
                  {w.toLocaleString()}
                </button>
              ))}
            </div>
          </label>
        </div>

        {/* Fast / Quality toggle */}
        <div className="mb-6">
          <span className="text-xs uppercase tracking-widest font-semibold mb-2 block" style={{ color: "var(--muted)" }}>
            Chế độ tạo
          </span>
          <div className="grid grid-cols-2 gap-2">
            {([
              { value: false, label: "⚡ Nhanh", desc: "Pipeline tiêu chuẩn" },
              { value: true, label: "✦ Chất lượng", desc: "+30-40% thời gian, prose tốt hơn" },
            ] as const).map(({ value, label, desc }) => (
              <button
                key={String(value)}
                type="button"
                onClick={() => setQualityMode(value)}
                className="py-2.5 px-3 rounded-sm text-sm font-semibold transition-all text-left"
                style={{
                  background: qualityMode === value ? "var(--amber)" : "var(--surface)",
                  color: qualityMode === value ? "var(--ink)" : "var(--subtle)",
                  border: `1px solid ${qualityMode === value ? "var(--amber)" : "var(--border)"}`,
                }}
              >
                <div>{label}</div>
                <div className="text-xs font-normal mt-0.5 opacity-70">{desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Style control — collapsible */}
        <div className="mb-6">
          <button
            type="button"
            onClick={() => setShowStyle((v) => !v)}
            className="flex items-center gap-2 text-xs uppercase tracking-widest font-semibold w-full text-left"
            style={{ color: showStyle ? "var(--amber)" : "var(--muted)" }}
          >
            <span>{showStyle ? "▾" : "▸"}</span>
            <span>Tùy chỉnh văn phong</span>
          </button>
          {showStyle && (
            <div className="mt-4 space-y-4 p-4 rounded-sm"
              style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
              <div>
                <span className="text-xs uppercase tracking-widest font-semibold block mb-2" style={{ color: "var(--muted)" }}>Tone</span>
                <div className="flex gap-2">
                  {(["light", "neutral", "tense"] as Tone[]).map((t) => {
                    const labels = { light: "Nhẹ nhàng", neutral: "Trung tính", tense: "Căng thẳng" };
                    return (
                      <button key={t} type="button" onClick={() => setTone(t)}
                        className="flex-1 py-2 rounded-sm text-sm font-semibold transition-all"
                        style={{
                          background: tone === t ? "var(--amber)" : "var(--paper)",
                          color: tone === t ? "var(--ink)" : "var(--subtle)",
                          border: `1px solid ${tone === t ? "var(--amber)" : "var(--border)"}`,
                        }}>
                        {labels[t]}
                      </button>
                    );
                  })}
                </div>
              </div>
              <div>
                <span className="text-xs uppercase tracking-widest font-semibold block mb-2" style={{ color: "var(--muted)" }}>Hội thoại</span>
                <div className="flex gap-2">
                  {(["low", "medium", "high"] as DialogueRatio[]).map((d) => {
                    const labels = { low: "Ít (~30%)", medium: "Vừa (~45%)", high: "Nhiều (~60%)" };
                    return (
                      <button key={d} type="button" onClick={() => setDialogueRatio(d)}
                        className="flex-1 py-2 rounded-sm text-sm font-semibold transition-all"
                        style={{
                          background: dialogueRatio === d ? "var(--amber)" : "var(--paper)",
                          color: dialogueRatio === d ? "var(--ink)" : "var(--subtle)",
                          border: `1px solid ${dialogueRatio === d ? "var(--amber)" : "var(--border)"}`,
                        }}>
                        {labels[d]}
                      </button>
                    );
                  })}
                </div>
              </div>
              <div>
                <span className="text-xs uppercase tracking-widest font-semibold block mb-2" style={{ color: "var(--muted)" }}>Ghi chú thêm</span>
                <input
                  type="text"
                  value={customNote}
                  onChange={(e) => setCustomNote(e.target.value)}
                  placeholder="Vd: Giữ nguyên giọng văn u ám của truyện gốc…"
                  className="w-full text-sm px-3 py-2 rounded-sm"
                  style={{ background: "var(--paper)", border: "1px solid var(--border)", color: "var(--body)" }}
                />
              </div>
            </div>
          )}
        </div>

        {error && (
          <p className="mb-4 text-sm px-4 py-2 rounded-sm" style={{ background: "var(--red-dim)", color: "#FCA5A5" }}>
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading || !(mode === "content" ? sourceContent.trim() : description.trim())}
          className="w-full py-4 rounded-sm text-base font-bold uppercase tracking-widest transition-all disabled:opacity-40"
          style={{ background: loading ? "var(--amber-dim)" : "var(--amber)", color: "var(--ink)", letterSpacing: "0.2em" }}
        >
          {loading ? (
            <span className="flex items-center justify-center gap-3">
              <span className="inline-block w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
              Đang khởi tạo…
            </span>
          ) : (
            "Viết tiếp →"
          )}
        </button>
      </form>

      <p className="fade-up mt-10 text-xs text-center" style={{ color: "var(--muted)", animationDelay: "0.2s", opacity: 0 }}>
        Powered by Gemini · Local-first
      </p>
    </main>
  );
}
