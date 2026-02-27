"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { API, WS_BASE } from "../lib/constants";

const GENRE_LABELS: Record<string, string> = {
  isekai: "Isekai", tu_tien: "Tu tiên",
  xuyen_khong: "Xuyên không", romance: "Romance",
};
const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  completed:   { label: "Hoàn thành", color: "#4ADE80" },
  failed:      { label: "Lỗi",        color: "#F87171" },
  drafting:    { label: "Đang viết",  color: "var(--amber)" },
  navigating_plot:    { label: "Phase 1",  color: "var(--amber)" },
  building_characters:{ label: "Phase 1",  color: "var(--amber)" },
  awaiting_plot_approval:   { label: "⏸ Chờ duyệt", color: "#F59E0B" },
  awaiting_chapter1_approval: { label: "⏸ Chờ duyệt", color: "#F59E0B" },
};

type Novel = {
  id: string; title: string | null; genre: string | null;
  status: string; chapter_count: number; total_words: number; created_at: string;
};
type CharProposal = {
  id: string; name: string; role: string;
  personality_traits: string[]; speech_pattern: string;
  backstory: string; goals: string[]; current_state: string;
};
type BlueprintSummary = {
  title: string; premise: string;
  chapters: { number: number; title: string; pov_character: string }[];
  characters: { name: string; role: string }[];
};

type ModalState =
  | { open: false }
  | { open: true; step: 1; novel: Novel; numChapters: number; genre: string; loading: boolean }
  | { open: true; step: 2; novel: Novel; chars: CharProposal[]; edited: CharProposal[]; loading: boolean }
  | { open: true; step: 3; novel: Novel; blueprint: BlueprintSummary; loading: boolean };

const IN_PROGRESS_STATUSES = [
  "navigating_plot", "building_characters", "drafting",
  "awaiting_plot_approval", "awaiting_chapter1_approval",
];

function formatDate(dt: string) {
  try { return new Date(dt).toLocaleDateString("vi-VN"); } catch { return dt; }
}

export default function NovelsPage() {
  const router = useRouter();
  const [novels, setNovels] = useState<Novel[]>([]);
  const [loading, setLoading] = useState(true);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [modal, setModal] = useState<ModalState>({ open: false });
  const [modalError, setModalError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const modalNovelIdRef = useRef<string | null>(null);

  useEffect(() => {
    fetch(`${API}/novels`)
      .then((r) => r.json())
      .then((data) => { setNovels(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  function connectWS(novelId: string) {
    wsRef.current?.close();
    const ws = new WebSocket(`${WS_BASE}/novels/${novelId}/ws`);
    wsRef.current = ws;
    ws.onmessage = (ev) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let event: any;
      try {
        event = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (event.type === "checkpoint_characters") {
        setModal((m) => m.open && m.novel.id === novelId
          ? { open: true, step: 2, novel: m.novel, chars: event.characters, edited: event.characters, loading: false }
          : m
        );
      } else if (event.type === "checkpoint_plot") {
        setModal((m) => m.open && m.novel.id === novelId
          ? { open: true, step: 3, novel: m.novel, blueprint: event.blueprint, loading: false }
          : m
        );
      } else if (event.type === "done") {
        wsRef.current?.close();
        router.push(`/write/${novelId}`);
      }
    };
    ws.onerror = (e) => { console.error("WS error:", e); };
    ws.onclose = () => {};
  }

  function openModal(novel: Novel) {
    modalNovelIdRef.current = novel.id;
    setModal({
      open: true, step: 1, novel,
      numChapters: 3, genre: novel.genre ?? "isekai", loading: false,
    });
    connectWS(novel.id);
  }

  function closeModal() {
    wsRef.current?.close();
    wsRef.current = null;
    modalNovelIdRef.current = null;
    setModal({ open: false });
    setModalError(null);
  }

  async function handleStartContinue() {
    if (!modal.open || modal.step !== 1) return;
    setModal((m) => m.open && m.step === 1 ? { ...m, loading: true } : m);
    setModalError(null);
    try {
      const res = await fetch(`${API}/novels/${modal.novel.id}/continue`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ num_chapters: modal.numChapters, genre: modal.genre }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      // WS will fire checkpoint_characters when ready
    } catch (err) {
      setModal((m) => m.open && m.step === 1 ? { ...m, loading: false } : m);
      setModalError(`Không thể bắt đầu: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  async function handleApproveCharacters() {
    if (!modal.open || modal.step !== 2) return;
    setModal((m) => m.open && m.step === 2 ? { ...m, loading: true } : m);
    setModalError(null);
    try {
      const res = await fetch(`${API}/novels/${modal.novel.id}/approve-characters`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ characters: modal.edited }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      // WS will fire checkpoint_plot
    } catch (err) {
      setModal((m) => m.open && m.step === 2 ? { ...m, loading: false } : m);
      setModalError(`Lỗi duyệt nhân vật: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  async function handleApprovePlot() {
    if (!modal.open || modal.step !== 3) return;
    setModal((m) => m.open && m.step === 3 ? { ...m, loading: true } : m);
    setModalError(null);
    try {
      const res = await fetch(`${API}/novels/${modal.novel.id}/approve-plot`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision: "approve" }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      // WS will fire done → navigate
    } catch (err) {
      setModal((m) => m.open && m.step === 3 ? { ...m, loading: false } : m);
      setModalError(`Lỗi duyệt cốt truyện: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  async function handleDelete(novelId: string) {
    try {
      await fetch(`${API}/novels/${novelId}`, { method: "DELETE" });
      setNovels((prev) => prev.filter((n) => n.id !== novelId));
    } catch (err) {
      console.error("Delete failed:", err);
    }
    setConfirmDelete(null);
  }

  function removeChar(idx: number) {
    if (!modal.open || modal.step !== 2) return;
    const edited = modal.edited.filter((_, i) => i !== idx);
    setModal((m) => m.open && m.step === 2 ? { ...m, edited } : m);
  }

  return (
    <div className="min-h-screen" style={{ background: "var(--ink)" }}>
      {/* ── Header ── */}
      <header className="flex items-center justify-between px-6 py-4 border-b"
        style={{ borderColor: "var(--border)", background: "var(--paper)" }}>
        <div className="flex items-center gap-4">
          <Link href="/" className="text-sm transition-colors" style={{ color: "var(--muted)" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "var(--amber)")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "var(--muted)")}>
            ← Trang chủ
          </Link>
          <span className="amber-rule" style={{ width: "1rem" }} />
          <h1 className="text-xl font-bold" style={{ fontFamily: "var(--font-playfair)", color: "var(--heading)" }}>
            Thư viện
          </h1>
        </div>
        <Link href="/"
          className="px-4 py-2 rounded-sm text-sm font-semibold uppercase tracking-wider"
          style={{ background: "var(--amber)", color: "var(--ink)" }}>
          + Viết mới
        </Link>
      </header>

      {/* ── Content ── */}
      <main className="max-w-5xl mx-auto px-6 py-10">
        {loading ? (
          <div className="flex justify-center py-24">
            <div className="w-8 h-8 border-2 border-t-transparent rounded-full animate-spin"
              style={{ borderColor: "var(--amber)", borderTopColor: "transparent" }} />
          </div>
        ) : novels.length === 0 ? (
          <div className="text-center py-24">
            <p className="text-lg mb-6" style={{ color: "var(--muted)" }}>Chưa có truyện nào.</p>
            <Link href="/"
              className="px-6 py-3 rounded-sm font-bold uppercase tracking-widest text-sm"
              style={{ background: "var(--amber)", color: "var(--ink)" }}>
              Viết truyện đầu tiên →
            </Link>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {novels.map((novel) => {
              const st = STATUS_LABELS[novel.status] ?? { label: novel.status, color: "var(--muted)" };
              const isDeleting = confirmDelete === novel.id;
              return (
                <div key={novel.id} className="rounded-sm p-5 flex flex-col gap-3"
                  style={{ background: "var(--paper)", border: "1px solid var(--border)" }}>
                  {/* Badges */}
                  <div className="flex items-center justify-between">
                    {novel.genre && (
                      <span className="text-xs px-2 py-0.5 rounded-full font-semibold"
                        style={{ background: "var(--surface)", color: "var(--amber)", border: "1px solid var(--amber)" }}>
                        {GENRE_LABELS[novel.genre] ?? novel.genre}
                      </span>
                    )}
                    <span className="text-xs font-semibold" style={{ color: st.color, marginLeft: "auto" }}>
                      ● {st.label}
                    </span>
                  </div>

                  {/* Title */}
                  <div>
                    <h2 className="text-base font-bold leading-snug mb-1"
                      style={{ fontFamily: "var(--font-playfair)", color: "var(--heading)" }}>
                      {novel.title ?? "Không có tên"}
                    </h2>
                    <p className="text-xs" style={{ color: "var(--muted)" }}>
                      {novel.chapter_count} chương · {novel.total_words.toLocaleString()} từ
                    </p>
                    <p className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>
                      {formatDate(novel.created_at)}
                    </p>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 mt-auto pt-2 border-t"
                    style={{ borderColor: "var(--border)" }}>
                    {IN_PROGRESS_STATUSES.includes(novel.status) ? (
                      <button onClick={() => router.push(`/write/${novel.id}`)}
                        className="flex-1 py-1.5 rounded-sm text-xs font-semibold transition-all"
                        style={{ background: "var(--amber)", color: "var(--ink)" }}>
                        Vào trang viết →
                      </button>
                    ) : novel.status === "completed" ? (
                      <>
                        <button onClick={() => router.push(`/novel/${novel.id}`)}
                          className="flex-1 py-1.5 rounded-sm text-xs font-semibold transition-all"
                          style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--subtle)" }}>
                          Đọc
                        </button>
                        <button onClick={() => openModal(novel)}
                          className="flex-1 py-1.5 rounded-sm text-xs font-semibold transition-all"
                          style={{ background: "var(--amber)", color: "var(--ink)" }}>
                          Viết tiếp ›
                        </button>
                      </>
                    ) : null /* failed — chỉ còn nút Xóa */}
                    <button
                      onClick={() => {
                        if (isDeleting) { handleDelete(novel.id); }
                        else { setConfirmDelete(novel.id); setTimeout(() => setConfirmDelete(null), 3000); }
                      }}
                      className="py-1.5 px-3 rounded-sm text-xs font-semibold transition-all"
                      style={{
                        background: isDeleting ? "#7F1D1D" : "var(--surface)",
                        border: `1px solid ${isDeleting ? "#F87171" : "var(--border)"}`,
                        color: isDeleting ? "#FCA5A5" : "var(--muted)",
                      }}>
                      {isDeleting ? "Chắc chắn?" : "Xóa"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* ── Continue Modal ── */}
      {modal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4"
          style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}>
          <div className="w-full max-w-lg rounded-sm p-6"
            style={{ background: "var(--paper)", border: "1px solid var(--border)" }}>
            {/* Modal header */}
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <span className="amber-rule" />
                <h2 className="text-lg font-bold" style={{ fontFamily: "var(--font-playfair)", color: "var(--heading)" }}>
                  {modal.step === 1 && "Viết tiếp"}
                  {modal.step === 2 && "Nhân vật mới"}
                  {modal.step === 3 && "Duyệt cốt truyện"}
                </h2>
              </div>
              <button onClick={closeModal} className="text-sm" style={{ color: "var(--muted)" }}>✕</button>
            </div>

            {/* Step indicator */}
            <div className="flex gap-2 mb-6">
              {[1, 2, 3].map((s) => (
                <div key={s} className="flex-1 h-1 rounded-full"
                  style={{ background: modal.step >= s ? "var(--amber)" : "var(--border)" }} />
              ))}
            </div>

            {modalError && (
              <div className="mb-4 px-3 py-2 rounded-sm text-xs"
                style={{ background: "#7f1d1d", color: "#FCA5A5" }}>
                {modalError}
              </div>
            )}

            {/* Step 1 — Config */}
            {modal.step === 1 && (
              <div className="space-y-5">
                <p className="text-sm" style={{ color: "var(--subtle)" }}>
                  Tiếp tục từ chương {modal.novel.chapter_count + 1} của{" "}
                  <span style={{ color: "var(--heading)" }}>{modal.novel.title}</span>
                </p>

                <div>
                  <p className="text-xs uppercase tracking-widest font-semibold mb-2" style={{ color: "var(--muted)" }}>
                    Thêm bao nhiêu chương?
                  </p>
                  <div className="flex gap-2">
                    {[3, 5, 10].map((n) => (
                      <button key={n} onClick={() => setModal((m) => m.open && m.step === 1 ? { ...m, numChapters: n } : m)}
                        className="flex-1 py-2 rounded-sm text-sm font-semibold transition-all"
                        style={{
                          background: modal.numChapters === n ? "var(--amber)" : "var(--surface)",
                          color: modal.numChapters === n ? "var(--ink)" : "var(--subtle)",
                          border: `1px solid ${modal.numChapters === n ? "var(--amber)" : "var(--border)"}`,
                        }}>
                        {n}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <p className="text-xs uppercase tracking-widest font-semibold mb-2" style={{ color: "var(--muted)" }}>
                    Thể loại
                  </p>
                  <div className="grid grid-cols-4 gap-2">
                    {(["isekai", "tu_tien", "xuyen_khong", "romance"] as const).map((g) => (
                      <button key={g} onClick={() => setModal((m) => m.open && m.step === 1 ? { ...m, genre: g } : m)}
                        className="py-2 rounded-sm text-xs font-semibold transition-all"
                        style={{
                          background: modal.genre === g ? "var(--amber)" : "var(--surface)",
                          color: modal.genre === g ? "var(--ink)" : "var(--subtle)",
                          border: `1px solid ${modal.genre === g ? "var(--amber)" : "var(--border)"}`,
                        }}>
                        {GENRE_LABELS[g]}
                      </button>
                    ))}
                  </div>
                </div>

                <button onClick={handleStartContinue} disabled={modal.loading}
                  className="w-full py-3 rounded-sm font-bold uppercase tracking-widest text-sm disabled:opacity-40"
                  style={{ background: "var(--amber)", color: "var(--ink)" }}>
                  {modal.loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                      Đang phân tích cốt truyện…
                    </span>
                  ) : "Bắt đầu →"}
                </button>
              </div>
            )}

            {/* Step 2 — Characters */}
            {modal.step === 2 && (
              <div className="space-y-4">
                {modal.chars.length === 0 ? (
                  <p className="text-sm py-4 text-center" style={{ color: "var(--muted)" }}>
                    AI không đề xuất nhân vật mới — nhân vật hiện tại đã đủ.
                  </p>
                ) : (
                  <div className="space-y-3 max-h-72 overflow-y-auto">
                    {modal.edited.map((char, idx) => (
                      <div key={char.id} className="p-3 rounded-sm flex items-start justify-between gap-3"
                        style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
                        <div>
                          <p className="text-sm font-semibold" style={{ color: "var(--heading)" }}>
                            {char.name}
                            <span className="ml-2 text-xs font-normal" style={{ color: "var(--muted)" }}>
                              {char.role}
                            </span>
                          </p>
                          <p className="text-xs mt-1 leading-relaxed" style={{ color: "var(--subtle)" }}>
                            {char.backstory}
                          </p>
                        </div>
                        <button onClick={() => removeChar(idx)}
                          className="text-xs flex-shrink-0 mt-0.5" style={{ color: "var(--muted)" }}>
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                <button onClick={handleApproveCharacters} disabled={modal.loading}
                  className="w-full py-3 rounded-sm font-bold uppercase tracking-widest text-sm disabled:opacity-40"
                  style={{ background: "var(--amber)", color: "var(--ink)" }}>
                  {modal.loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                      Đang lên kế hoạch…
                    </span>
                  ) : `Xác nhận ${modal.edited.length > 0 ? `${modal.edited.length} nhân vật` : "— không thêm mới"} →`}
                </button>
              </div>
            )}

            {/* Step 3 — Plot approval */}
            {modal.step === 3 && (
              <div className="space-y-4">
                <div className="space-y-2 max-h-72 overflow-y-auto">
                  {modal.blueprint.chapters
                    .filter((ch) => ch.number > (modal.novel.chapter_count))
                    .map((ch) => (
                      <div key={ch.number} className="px-3 py-2 rounded-sm text-sm"
                        style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--subtle)" }}>
                        <span style={{ color: "var(--amber)" }}>{ch.number}. </span>
                        <span style={{ color: "var(--body)" }}>{ch.title}</span>
                        <span style={{ color: "var(--muted)" }}> · POV: {ch.pov_character}</span>
                      </div>
                    ))}
                </div>

                <button onClick={handleApprovePlot} disabled={modal.loading}
                  className="w-full py-3 rounded-sm font-bold uppercase tracking-widest text-sm disabled:opacity-40"
                  style={{ background: "var(--amber)", color: "var(--ink)" }}>
                  {modal.loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                      Đang khởi động…
                    </span>
                  ) : "Bắt đầu viết →"}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
