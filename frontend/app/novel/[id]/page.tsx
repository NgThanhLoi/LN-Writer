"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";

import { API } from "../../lib/constants";

type Chapter = {
  number: number;
  title: string;
  content: string;
  audit_passed: boolean;
  audit_notes: string;
  word_count: number;
};

type NovelMeta = {
  id: string;
  status: string;
  current_chapter: number;
  title: string | null;
  premise: string | null;
};

export default function ReaderPage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();

  const [novel, setNovel] = useState<NovelMeta | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [activeChapter, setActiveChapter] = useState<number>(
    parseInt(searchParams.get("ch") ?? "1", 10)
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [regenning, setRegenning] = useState<number | null>(null);
  const [regenMsg, setRegenMsg] = useState("");

  // ── Theme ──────────────────────────────────────────────────────────────
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const saved = localStorage.getItem("ln-theme") as "dark" | "light" | null;
    const initial = saved ?? "dark";
    setTheme(initial);
    document.documentElement.setAttribute("data-theme", initial);
  }, []);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("ln-theme", next);
    document.documentElement.setAttribute("data-theme", next);
  }

  // ── Load data ───────────────────────────────────────────────────────────
  useEffect(() => {
    async function load() {
      try {
        const [novelRes, chaptersRes] = await Promise.all([
          fetch(`${API}/novels/${id}`),
          fetch(`${API}/novels/${id}/chapters`),
        ]);
        if (!novelRes.ok) throw new Error("Novel not found");
        setNovel(await novelRes.json());
        const chs: Chapter[] = await chaptersRes.json();
        setChapters(chs);
        if (chs.length > 0 && !chs.find((c) => c.number === activeChapter)) {
          setActiveChapter(chs[0].number);
        }
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Keyboard navigation ────────────────────────────────────────────────
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLInputElement) return;
      if (e.key === "ArrowLeft" && activeChapter > 1) {
        setActiveChapter((n) => n - 1);
      } else if (e.key === "ArrowRight" && activeChapter < chapters.length) {
        setActiveChapter((n) => n + 1);
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [activeChapter, chapters.length]);

  // ── Chapter editor ─────────────────────────────────────────────────────
  const [editingChapter, setEditingChapter] = useState<number | null>(null);
  const [editContent, setEditContent] = useState("");
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved">("idle");
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const autoSave = useCallback(
    (chapterNumber: number, content: string) => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      setSaveStatus("saving");
      saveTimerRef.current = setTimeout(async () => {
        try {
          const res = await fetch(`${API}/novels/${id}/chapters/${chapterNumber}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content }),
          });
          if (!res.ok) throw new Error();
          setChapters((prev) =>
            prev.map((c) =>
              c.number === chapterNumber
                ? { ...c, content, word_count: content.split(/\s+/).filter(Boolean).length }
                : c
            )
          );
          setSaveStatus("saved");
          setTimeout(() => setSaveStatus("idle"), 2000);
        } catch {
          setSaveStatus("idle");
        }
      }, 500);
    },
    [id]
  );

  function startEdit(ch: Chapter) {
    setEditingChapter(ch.number);
    setEditContent(ch.content);
    setSaveStatus("idle");
  }

  function cancelEdit() {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    setEditingChapter(null);
    setSaveStatus("idle");
  }

  function handleEditChange(value: string) {
    setEditContent(value);
    if (editingChapter !== null) autoSave(editingChapter, value);
  }

  // ── Regen ───────────────────────────────────────────────────────────────
  async function handleRegen(chapterNumber: number) {
    if (editingChapter === chapterNumber) cancelEdit();
    setRegenning(chapterNumber);
    setRegenMsg("");
    try {
      const res = await fetch(`${API}/novels/${id}/chapters/${chapterNumber}/regen`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(await res.text());
      setRegenMsg(`Đang viết lại chương ${chapterNumber}… Tải lại trang sau ít phút để xem kết quả.`);
    } catch (e: unknown) {
      setRegenMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setRegenning(null);
    }
  }

  async function handleDownload() {
    const a = document.createElement("a");
    a.href = `${API}/novels/${id}/download`;
    a.download = "";
    a.click();
  }

  // ── Loading / Error states ──────────────────────────────────────────────
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div
            className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin mx-auto mb-4"
            style={{ borderColor: "var(--amber)", borderTopColor: "transparent" }}
          />
          <p style={{ color: "var(--muted)" }}>Đang tải…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p
          className="text-sm px-6 py-3 rounded-sm"
          style={{ background: "var(--red-dim)", color: "#FCA5A5" }}
        >
          {error}
        </p>
      </div>
    );
  }

  const currentChapter = chapters.find((c) => c.number === activeChapter);
  const totalWords = chapters.reduce((acc, c) => acc + c.word_count, 0);

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--ink)" }}>
      {/* ── Header ── */}
      <header
        className="flex items-center justify-between px-6 py-4 border-b"
        style={{ borderColor: "var(--border)", background: "var(--paper)" }}
      >
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="text-sm transition-colors"
            style={{ color: "var(--muted)" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "var(--amber)")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "var(--muted)")}
          >
            ← Trang chủ
          </Link>
          <span className="amber-rule" style={{ width: "1rem" }} />
          <div>
            <h1
              className="text-xl font-bold"
              style={{ fontFamily: "var(--font-playfair)", color: "var(--heading)" }}
            >
              {novel?.title ?? "Light Novel"}
            </h1>
            {novel?.premise && (
              <p className="text-xs mt-0.5 max-w-md truncate" style={{ color: "var(--muted)" }}>
                {novel.premise}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs hidden sm:block" style={{ color: "var(--muted)" }}>
            {chapters.length} chương · {totalWords.toLocaleString()} từ
          </span>

          {/* Theme toggle */}
          <button
            onClick={toggleTheme}
            title={theme === "dark" ? "Chuyển sang chế độ sáng" : "Chuyển sang chế độ tối"}
            className="w-8 h-8 flex items-center justify-center rounded-sm text-sm transition-all"
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              color: "var(--subtle)",
            }}
          >
            {theme === "dark" ? "☀" : "☾"}
          </button>

          {novel?.status === "completed" && (
            <button
              onClick={handleDownload}
              className="px-4 py-2 rounded-sm text-sm font-semibold uppercase tracking-wider transition-all"
              style={{
                background: "transparent",
                border: "1px solid var(--amber)",
                color: "var(--amber)",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.background = "var(--amber)";
                (e.currentTarget as HTMLButtonElement).style.color = "var(--ink)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.background = "transparent";
                (e.currentTarget as HTMLButtonElement).style.color = "var(--amber)";
              }}
            >
              Tải xuống .md
            </button>
          )}
        </div>
      </header>

      {/* ── Body ── */}
      <div className="flex flex-1 overflow-hidden">
        {/* ── Sidebar ── */}
        <nav
          className="w-56 border-r overflow-y-auto flex-shrink-0 hidden md:block"
          style={{ borderColor: "var(--border)", background: "var(--paper)" }}
        >
          <div className="px-4 pt-5 pb-3">
            <p
              className="text-xs uppercase tracking-widest font-semibold"
              style={{ color: "var(--muted)" }}
            >
              Mục lục
            </p>
          </div>
          <div className="pb-4">
            {chapters.map((ch) => {
              const isActive = activeChapter === ch.number;
              return (
                <button
                  key={ch.number}
                  onClick={() => setActiveChapter(ch.number)}
                  className="w-full text-left px-4 py-3 text-sm transition-all"
                  style={{
                    background: isActive ? "var(--surface)" : "transparent",
                    borderLeft: `2px solid ${isActive ? "var(--amber)" : "transparent"}`,
                    color: isActive ? "var(--heading)" : "var(--subtle)",
                  }}
                >
                  <div className="text-xs mb-0.5" style={{ color: "var(--muted)" }}>
                    Chương {ch.number}
                  </div>
                  <div className="leading-snug">{ch.title}</div>
                  <div className="flex items-center justify-between mt-1">
                    <span
                      className="text-xs font-semibold px-1.5 py-0.5 rounded-sm"
                      style={{
                        background: isActive ? "var(--amber-glow)" : "var(--border)",
                        color: isActive ? "var(--amber)" : "var(--muted)",
                      }}
                    >
                      {ch.word_count.toLocaleString()} từ
                    </span>
                    {!ch.audit_passed && (
                      <span className="text-xs" style={{ color: "#F87171" }}>⚠</span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </nav>

        {/* ── Reader area ── */}
        <main className="flex-1 overflow-y-auto">
          {currentChapter ? (
            <article className="mx-auto px-6 py-12" style={{ maxWidth: "70ch" }}>
              {/* Chapter header */}
              <div className="mb-10">
                <p
                  className="text-xs uppercase tracking-widest font-semibold mb-2"
                  style={{ color: "var(--amber)" }}
                >
                  Chương {currentChapter.number}
                </p>
                <h2
                  className="text-3xl md:text-4xl font-bold mb-3"
                  style={{ fontFamily: "var(--font-playfair)", color: "var(--heading)" }}
                >
                  {currentChapter.title}
                </h2>

                {/* Word count + audit badge row */}
                <div className="flex items-center gap-3 mb-4">
                  <span
                    className="text-xs font-semibold px-2.5 py-1 rounded-sm"
                    style={{
                      background: "var(--amber-glow)",
                      color: "var(--amber)",
                      border: "1px solid var(--amber-dim)",
                    }}
                  >
                    {currentChapter.word_count.toLocaleString()} từ
                  </span>
                  <span
                    className="text-xs"
                    style={{ color: currentChapter.audit_passed ? "#4ADE80" : "#F87171" }}
                  >
                    {currentChapter.audit_passed ? "✓ Audit passed" : "⚠ Audit failed"}
                  </span>
                  {saveStatus === "saving" && (
                    <span className="text-xs" style={{ color: "var(--amber)" }}>Đang lưu…</span>
                  )}
                  {saveStatus === "saved" && (
                    <span className="text-xs" style={{ color: "#4ADE80" }}>✓ Đã lưu</span>
                  )}
                </div>

                {/* Actions row */}
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div />

                  <div className="flex items-center gap-2">
                    {/* Edit toggle */}
                    {editingChapter === currentChapter.number ? (
                      <button
                        onClick={cancelEdit}
                        className="text-xs px-3 py-1 rounded-sm transition-all"
                        style={{
                          background: "var(--surface)",
                          border: "1px solid var(--border)",
                          color: "var(--subtle)",
                        }}
                      >
                        ✕ Đóng
                      </button>
                    ) : (
                      <button
                        onClick={() => startEdit(currentChapter)}
                        disabled={regenning === currentChapter.number}
                        className="text-xs px-3 py-1 rounded-sm transition-all disabled:opacity-40"
                        style={{
                          background: "var(--surface)",
                          border: "1px solid var(--border)",
                          color: "var(--subtle)",
                        }}
                      >
                        ✎ Chỉnh sửa
                      </button>
                    )}

                    {/* Regen */}
                    <button
                      onClick={() => handleRegen(currentChapter.number)}
                      disabled={regenning === currentChapter.number}
                      className="text-xs px-3 py-1 rounded-sm transition-all disabled:opacity-40"
                      style={{
                        background: "var(--surface)",
                        border: "1px solid var(--border)",
                        color: "var(--muted)",
                      }}
                    >
                      {regenning === currentChapter.number ? "Đang viết lại…" : "↻ Viết lại"}
                    </button>
                  </div>
                </div>

                {regenMsg && (
                  <p className="mt-2 text-xs" style={{ color: "var(--amber)" }}>
                    {regenMsg}
                  </p>
                )}
                <div className="mt-4 h-px" style={{ background: "var(--border)" }} />
              </div>

              {/* Editor or reader */}
              {editingChapter === currentChapter.number ? (
                <textarea
                  value={editContent}
                  onChange={(e) => handleEditChange(e.target.value)}
                  className="w-full rounded-sm resize-none px-4 py-4 focus:outline-none"
                  rows={Math.max(20, editContent.split("\n").length + 5)}
                  style={{
                    background: "var(--surface)",
                    border: "1px solid var(--border)",
                    color: "var(--body)",
                    fontFamily: "var(--font-playfair)",
                    fontSize: "1.05rem",
                    lineHeight: "1.8",
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
              ) : (
                <div
                  className="max-w-none"
                  style={{
                    fontFamily: "var(--font-playfair)",
                    color: "var(--body)",
                    lineHeight: "1.8",
                    fontSize: "1.05rem",
                  }}
                >
                  {currentChapter.content.split("\n").map((para, i) =>
                    para.trim() ? (
                      <p key={i} className="mb-5">
                        {para}
                      </p>
                    ) : null
                  )}
                </div>
              )}

              {/* Prev / Next navigation */}
              <div
                className="flex items-center justify-between mt-12 pt-6"
                style={{ borderTop: "1px solid var(--border)" }}
              >
                {activeChapter > 1 ? (
                  <button
                    onClick={() => setActiveChapter(activeChapter - 1)}
                    className="text-sm px-4 py-2 rounded-sm transition-all"
                    style={{
                      background: "var(--surface)",
                      border: "1px solid var(--border)",
                      color: "var(--subtle)",
                    }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--amber)";
                      (e.currentTarget as HTMLButtonElement).style.color = "var(--amber)";
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--border)";
                      (e.currentTarget as HTMLButtonElement).style.color = "var(--subtle)";
                    }}
                  >
                    ← Chương {activeChapter - 1}
                  </button>
                ) : (
                  <div />
                )}

                <span className="text-xs" style={{ color: "var(--muted)" }}>
                  {activeChapter} / {chapters.length}
                  <span className="hidden sm:inline ml-1">(← → để điều hướng)</span>
                </span>

                {activeChapter < chapters.length ? (
                  <button
                    onClick={() => setActiveChapter(activeChapter + 1)}
                    className="text-sm px-4 py-2 rounded-sm font-semibold transition-all"
                    style={{ background: "var(--amber)", color: "var(--ink)" }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLButtonElement).style.background = "var(--amber-dim)";
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLButtonElement).style.background = "var(--amber)";
                    }}
                  >
                    Chương {activeChapter + 1} →
                  </button>
                ) : (
                  <span className="text-sm" style={{ color: "var(--muted)" }}>
                    Hết
                  </span>
                )}
              </div>
            </article>
          ) : (
            <div className="flex items-center justify-center h-full">
              <p style={{ color: "var(--muted)" }}>Chưa có chương nào.</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
