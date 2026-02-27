"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { API } from "./lib/constants";

type Tone = "light" | "neutral" | "tense";
type DialogueRatio = "low" | "medium" | "high";

export default function LandingPage() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
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
    if (!prompt.trim()) return;
    setLoading(true);
    setError("");

    try {
      const res = await fetch(`${API}/novels`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: prompt.trim(),
          num_chapters: chapters,
          words_per_chapter: words,
          genre,
          style_config: { tone, dialogue_ratio: dialogueRatio, custom_note: customNote, quality_mode: qualityMode },
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const { id } = await res.json();
      router.push(`/write/${id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-6 py-16">
      {/* ── Nav ── */}
      <div className="absolute top-6 right-6 flex items-center gap-4">
        <a href="/import" className="text-sm font-semibold transition-colors"
          style={{ color: "var(--subtle)" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--amber)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--subtle)")}>
          Tiếp nối truyện
        </a>
        <a href="/novels" className="text-sm font-semibold uppercase tracking-widest transition-colors"
          style={{ color: "var(--muted)" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--amber)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--muted)")}>
          Thư viện →
        </a>
      </div>

      {/* ── Header ── */}
      <div className="fade-up text-center mb-16">
        <div className="flex items-center justify-center gap-3 mb-4">
          <span className="amber-rule" />
          <span
            className="text-xs uppercase tracking-[0.25em] font-semibold"
            style={{ color: "var(--amber)" }}
          >
            AI Light Novel Studio
          </span>
          <span className="amber-rule" />
        </div>
        <h1
          className="text-5xl md:text-7xl font-bold leading-tight mb-4"
          style={{ fontFamily: "var(--font-playfair)", color: "var(--heading)" }}
        >
          LN Writer
        </h1>
        <p className="text-lg max-w-md mx-auto" style={{ color: "var(--subtle)" }}>
          Biến ý tưởng thành light novel tiếng Việt — có nhân vật, world-building,
          và cliffhanger — chỉ với một prompt.
        </p>
      </div>

      {/* ── Form ── */}
      <form
        onSubmit={handleSubmit}
        className="fade-up w-full max-w-2xl"
        style={{ animationDelay: "0.1s", opacity: 0 }}
      >
        {/* Prompt textarea */}
        <div className="relative mb-6">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Một học sinh cấp 3 bị isekai vào thế giới game fantasy…"
            rows={5}
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
          <div
            className="absolute bottom-3 right-4 text-xs"
            style={{ color: "var(--muted)" }}
          >
            {prompt.length} ký tự
          </div>
        </div>

        {/* Genre selector */}
        <div className="mb-6">
          <span className="text-xs uppercase tracking-widest font-semibold mb-2 block"
            style={{ color: "var(--muted)" }}>
            Thể loại
          </span>
          <div className="grid grid-cols-3 gap-2">
            {(["isekai", "tu_tien", "xuyen_khong", "romance", "kinh_di", "hanh_dong"] as const).map((g) => {
              const labels: Record<string, string> = {
                isekai: "Isekai", tu_tien: "Tu tiên",
                xuyen_khong: "Xuyên không", romance: "Romance",
                kinh_di: "Kinh dị", hanh_dong: "Hành động",
              };
              return (
                <button key={g} type="button" onClick={() => setGenre(g)}
                  className="py-2 rounded-sm text-sm font-semibold transition-all"
                  style={{
                    background: genre === g ? "var(--amber)" : "var(--surface)",
                    color: genre === g ? "var(--ink)" : "var(--subtle)",
                    border: `1px solid ${genre === g ? "var(--amber)" : "var(--border)"}`,
                  }}>
                  {labels[g]}
                </button>
              );
            })}
          </div>
        </div>

        {/* Options row */}
        <div className="grid grid-cols-2 gap-4 mb-8">
          <label className="flex flex-col gap-2">
            <span className="text-xs uppercase tracking-widest font-semibold"
              style={{ color: "var(--muted)" }}>
              Số chương
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
            <span className="text-xs uppercase tracking-widest font-semibold"
              style={{ color: "var(--muted)" }}>
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
              {/* Tone */}
              <div>
                <span className="text-xs uppercase tracking-widest font-semibold block mb-2"
                  style={{ color: "var(--muted)" }}>Tone</span>
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

              {/* Dialogue ratio */}
              <div>
                <span className="text-xs uppercase tracking-widest font-semibold block mb-2"
                  style={{ color: "var(--muted)" }}>Hội thoại</span>
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

              {/* Custom note */}
              <div>
                <span className="text-xs uppercase tracking-widest font-semibold block mb-2"
                  style={{ color: "var(--muted)" }}>Ghi chú thêm (tuỳ chọn)</span>
                <input
                  type="text"
                  value={customNote}
                  onChange={(e) => setCustomNote(e.target.value)}
                  placeholder="Vd: Tập trung cảm xúc nhân vật, ít hành động..."
                  className="w-full text-sm px-3 py-2 rounded-sm"
                  style={{
                    background: "var(--paper)",
                    border: "1px solid var(--border)",
                    color: "var(--body)",
                  }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Fast / Quality toggle */}
        <div className="mb-6">
          <span className="text-xs uppercase tracking-widest font-semibold mb-2 block"
            style={{ color: "var(--muted)" }}>
            Chế độ tạo
          </span>
          <div className="grid grid-cols-2 gap-2">
            {([
              { value: false, label: "⚡ Nhanh", desc: "Pipeline tiêu chuẩn" },
              { value: true,  label: "✦ Chất lượng", desc: "+30-40% thời gian, prose tốt hơn" },
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

        {error && (
          <p className="mb-4 text-sm px-4 py-2 rounded-sm"
            style={{ background: "var(--red-dim)", color: "#FCA5A5" }}>
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading || !prompt.trim()}
          className="w-full py-4 rounded-sm text-base font-bold uppercase tracking-widest transition-all disabled:opacity-40"
          style={{
            background: loading ? "var(--amber-dim)" : "var(--amber)",
            color: "var(--ink)",
            letterSpacing: "0.2em",
          }}
        >
          {loading ? (
            <span className="flex items-center justify-center gap-3">
              <span className="inline-block w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
              Đang khởi tạo…
            </span>
          ) : (
            "Bắt đầu viết"
          )}
        </button>
      </form>

      {/* ── Footer note ── */}
      <p
        className="fade-up mt-12 text-xs text-center"
        style={{ color: "var(--muted)", animationDelay: "0.2s", opacity: 0 }}
      >
        Powered by Gemini · Local-first · Dữ liệu lưu local
      </p>
    </main>
  );
}
