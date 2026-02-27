"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { API, WS_BASE } from "../../lib/constants";

type LogEntry = { msg: string; ts: number };
type ChapterMeta = {
  number: number;
  title: string;
  word_count: number;
  audit_passed: boolean;
  audit_notes: string;
};
type BlueprintSummary = {
  title: string;
  premise: string;
  world_summary: string;
  chapters: { number: number; title: string; pov_character: string; opening_hook: string; ending_cliffhanger: string }[];
  characters: { name: string; role: string; personality_traits: string[]; core_value: string; fear: string }[];
};
type CheckpointPlotData = { blueprint: BlueprintSummary };
type CheckpointChapter1Data = { preview: string; word_count: number; audit_passed: boolean; audit_notes: string };

type WritingProgress = { chapter_number: number; chapter_title: string; words_so_far: number; target: number };

type WSEvent =
  | { type: "status"; status: string; current_chapter?: number }
  | { type: "log"; msg: string }
  | { type: "chapter_done"; number: number; title: string; word_count: number; audit_passed: boolean; audit_notes: string }
  | { type: "checkpoint_plot"; blueprint: BlueprintSummary }
  | { type: "checkpoint_chapter1"; preview: string; word_count: number; audit_passed: boolean; audit_notes: string }
  | { type: "done"; status: string; output_path?: string; total_words?: number }
  | { type: "error"; msg: string }
  | { type: "regen_start"; chapter_number: number }
  | { type: "regen_done"; chapter_number: number; title: string; word_count: number; audit_passed: boolean; audit_notes: string }
  | { type: "chapter_progress"; chapter_number: number; chapter_title: string; words_so_far: number; target: number }
  | { type: "ping" };

export default function WritePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [status, setStatus] = useState("connecting");
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [chapters, setChapters] = useState<ChapterMeta[]>([]);
  const [blueprint, setBlueprint] = useState<BlueprintSummary | null>(null);
  const [plotCheckpoint, setPlotCheckpoint] = useState<CheckpointPlotData | null>(null);
  const [ch1Checkpoint, setCh1Checkpoint] = useState<CheckpointChapter1Data | null>(null);
  const [finalStats, setFinalStats] = useState<{ total_words: number } | null>(null);
  const [writingProgress, setWritingProgress] = useState<WritingProgress | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const phase1StartRef = useRef<number | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const intentionalCloseRef = useRef(false);
  const lastSeqRef = useRef(0);
  const MAX_RETRIES = 5;

  useEffect(() => {
    function connect() {
      const ws = new WebSocket(`${WS_BASE}/novels/${id}/ws`);
      wsRef.current = ws;

      ws.onopen = () => {
        retriesRef.current = 0;
        setStatus((s) => s === "connecting" || s === "reconnecting" ? "connecting" : s);
      };

      ws.onmessage = (ev) => {
        let event: WSEvent & { seq?: number };
        try {
          event = JSON.parse(ev.data);
        } catch {
          return; // ignore malformed messages
        }
        if (event.type === "ping") return;
        if (event.seq !== undefined) {
          if (event.seq <= lastSeqRef.current) return;
          lastSeqRef.current = event.seq;
        }

        if (event.type === "status") {
          setStatus(event.status);
        } else if (event.type === "log") {
          setLogs((prev) => [...prev, { msg: event.msg, ts: Date.now() }]);
        } else if (event.type === "chapter_done") {
          setWritingProgress(null);
          setChapters((prev) => {
            const exists = prev.find((c) => c.number === event.number);
            if (exists) return prev;
            return [...prev, { number: event.number, title: event.title, word_count: event.word_count, audit_passed: event.audit_passed, audit_notes: event.audit_notes }];
          });
        } else if (event.type === "checkpoint_plot") {
          setBlueprint(event.blueprint);
          setPlotCheckpoint({ blueprint: event.blueprint });
        } else if (event.type === "checkpoint_chapter1") {
          setCh1Checkpoint({ preview: event.preview, word_count: event.word_count, audit_passed: event.audit_passed, audit_notes: event.audit_notes });
        } else if (event.type === "done") {
          setStatus(event.status);
          if (event.total_words) setFinalStats({ total_words: event.total_words });
        } else if (event.type === "error") {
          setStatus("failed");
        } else if (event.type === "chapter_progress") {
          setWritingProgress({ chapter_number: event.chapter_number, chapter_title: event.chapter_title, words_so_far: event.words_so_far, target: event.target });
        } else if (event.type === "regen_start") {
          setWritingProgress(null);
          setLogs((prev) => [...prev, { msg: `↻ Đang viết lại chương ${event.chapter_number}…`, ts: Date.now() }]);
        } else if (event.type === "regen_done") {
          setWritingProgress(null);
          setChapters((prev) => prev.map((c) =>
            c.number === event.chapter_number
              ? { ...c, word_count: event.word_count, audit_passed: event.audit_passed, audit_notes: event.audit_notes }
              : c
          ));
          setLogs((prev) => [...prev, {
            msg: `✓ Chương ${event.chapter_number} viết lại xong — ${event.word_count.toLocaleString()} từ`,
            ts: Date.now(),
          }]);
        }
      };

      ws.onclose = () => {
        if (intentionalCloseRef.current) return;
        setStatus((s) => {
          if (s === "completed" || s === "failed") return s;
          if (retriesRef.current < MAX_RETRIES) {
            retriesRef.current += 1;
            const delay = Math.min(1000 * retriesRef.current, 5000);
            setTimeout(connect, delay);
            return "reconnecting";
          }
          return "disconnected";
        });
      };

      ws.onerror = () => { /* handled in onclose */ };
    }

    intentionalCloseRef.current = false;
    connect();

    return () => {
      intentionalCloseRef.current = true;
      wsRef.current?.close();
    };
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const [cancelling, setCancelling] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  async function cancelNovel() {
    if (!confirm("Huỷ và xoá novel này?")) return;
    setCancelling(true);
    try {
      await fetch(`${API}/novels/${id}`, { method: "DELETE" });
      router.push("/novels");
    } catch (err) {
      setCancelling(false);
      setActionError(`Huỷ thất bại: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  async function approvePlot(decision: "approve" | "reject") {
    try {
      await fetch(`${API}/novels/${id}/approve-plot`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision }),
      });
      setPlotCheckpoint(null);
    } catch (err) {
      setActionError(`Lỗi duyệt cốt truyện: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  async function approveChapter1(action: "approve" | "skip" | "regen") {
    try {
      await fetch(`${API}/novels/${id}/approve-chapter-1`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      setCh1Checkpoint(null);
    } catch (err) {
      setActionError(`Lỗi duyệt chương 1: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  const isRunning = !["completed", "failed", "disconnected", "reconnecting"].includes(status);
  const isPhase1 = status === "navigating_plot" || status === "building_characters";

  useEffect(() => {
    if (isPhase1) {
      if (!phase1StartRef.current) phase1StartRef.current = Date.now();
      const interval = setInterval(() => {
        setElapsedSeconds(Math.floor((Date.now() - phase1StartRef.current!) / 1000));
      }, 1000);
      return () => clearInterval(interval);
    } else {
      phase1StartRef.current = null;
      setElapsedSeconds(0);
    }
  }, [isPhase1]);

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--ink)" }}>
      {/* ── Top bar ── */}
      <header
        className="flex items-center justify-between px-6 py-3 border-b"
        style={{ borderColor: "var(--border)", background: "var(--paper)" }}
      >
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold" style={{ fontFamily: "var(--font-playfair)", color: "var(--heading)" }}>
            LN Writer
          </span>
          <span className="amber-rule" style={{ width: "1rem" }} />
          <span className="text-sm" style={{ color: "var(--subtle)" }}>
            {blueprint?.title ?? "Đang xử lý…"}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={status} />
          {isRunning && !plotCheckpoint && !ch1Checkpoint && (
            <button
              onClick={cancelNovel}
              disabled={cancelling}
              className="text-xs px-3 py-1 rounded-sm"
              style={{ border: "1px solid var(--border)", color: "var(--muted)", background: "transparent" }}
            >
              {cancelling ? "Đang huỷ…" : "Huỷ"}
            </button>
          )}
        </div>
      </header>

      {actionError && (
        <div className="px-6 py-2 text-sm flex items-center justify-between"
          style={{ background: "#7f1d1d", color: "#FCA5A5" }}>
          <span>{actionError}</span>
          <button onClick={() => setActionError(null)} style={{ marginLeft: "1rem", opacity: 0.7 }}>✕</button>
        </div>
      )}

      {/* ── Body: 2-panel layout ── */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Blueprint panel */}
        <aside
          className="w-72 border-r overflow-y-auto p-5 flex-shrink-0 hidden md:block"
          style={{ borderColor: "var(--border)", background: "var(--paper)" }}
        >
          {blueprint ? (
            <BlueprintPanel blueprint={blueprint} chapters={chapters} />
          ) : (
            <div className="text-sm" style={{ color: "var(--muted)" }}>
              Blueprint sẽ xuất hiện sau Phase 1…
            </div>
          )}
        </aside>

        {/* Right: Log + content area */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {/* Chapter list */}
          {chapters.length > 0 && (
            <div
              className="border-b px-6 py-3 flex gap-4 overflow-x-auto flex-shrink-0"
              style={{ borderColor: "var(--border)" }}
            >
              {chapters.map((ch) => (
                <button
                  key={ch.number}
                  onClick={() => router.push(`/novel/${id}?ch=${ch.number}`)}
                  title={!ch.audit_passed && ch.audit_notes ? ch.audit_notes : undefined}
                  className="flex-shrink-0 text-sm px-3 py-1 rounded-sm transition-all"
                  style={{
                    background: "var(--surface)",
                    border: `1px solid ${ch.audit_passed ? "var(--amber)" : "var(--border)"}`,
                    color: ch.audit_passed ? "var(--amber)" : "var(--subtle)",
                  }}
                >
                  Ch.{ch.number} · {ch.word_count.toLocaleString()} từ{!ch.audit_passed ? " ⚠" : ""}
                </button>
              ))}
            </div>
          )}

          {/* Log stream */}
          <div className="flex-1 overflow-y-auto px-6 py-5 space-y-1">
            {logs.map((l, i) => (
              <p key={i} className="text-sm font-mono leading-relaxed" style={{ color: "var(--subtle)" }}>
                <span style={{ color: "var(--muted)", marginRight: "0.75rem" }}>›</span>
                {l.msg}
              </p>
            ))}
            {isRunning && isPhase1 ? (
              <Phase1Timer status={status} elapsed={elapsedSeconds} />
            ) : isRunning && writingProgress ? (
              <ChapterProgressBar progress={writingProgress} />
            ) : isRunning ? (
              <p className="text-sm font-mono" style={{ color: "var(--subtle)" }}>
                <span style={{ color: "var(--muted)", marginRight: "0.75rem" }}>›</span>
                <span className="cursor-blink" />
              </p>
            ) : null}
            <div ref={logsEndRef} />
          </div>

          {/* Completion banner */}
          {status === "completed" && finalStats && (
            <div
              className="m-4 px-6 py-4 rounded-sm flex items-center justify-between"
              style={{ background: "var(--surface)", border: "1px solid var(--amber)" }}
            >
              <div>
                <p className="font-semibold" style={{ fontFamily: "var(--font-playfair)", color: "var(--heading)" }}>
                  Hoàn thành!
                </p>
                <p className="text-sm" style={{ color: "var(--subtle)" }}>
                  {finalStats.total_words.toLocaleString()} từ · {chapters.length} chương
                </p>
              </div>
              <button
                onClick={() => router.push(`/novel/${id}`)}
                className="px-5 py-2 rounded-sm text-sm font-bold uppercase tracking-wider"
                style={{ background: "var(--amber)", color: "var(--ink)" }}
              >
                Đọc ngay
              </button>
            </div>
          )}

          {status === "reconnecting" && (
            <div className="m-4 px-4 py-3 rounded-sm text-sm"
              style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--muted)" }}>
              Mất kết nối — đang thử lại…
            </div>
          )}
          {status === "disconnected" && (
            <div className="m-4 px-4 py-3 rounded-sm text-sm flex items-center justify-between"
              style={{ background: "var(--red-dim)", color: "#FCA5A5" }}>
              <span>Mất kết nối sau nhiều lần thử.</span>
              <button
                onClick={() => window.location.reload()}
                className="ml-4 px-3 py-1 rounded-sm text-xs font-semibold"
                style={{ background: "#FCA5A5", color: "#7f1d1d" }}
              >
                Tải lại trang
              </button>
            </div>
          )}
        </main>
      </div>

      {/* ── Checkpoint modals ── */}
      {plotCheckpoint && (
        <PlotApprovalModal
          data={plotCheckpoint}
          onApprove={() => approvePlot("approve")}
          onReject={() => approvePlot("reject")}
        />
      )}
      {ch1Checkpoint && (
        <Chapter1ApprovalModal
          data={ch1Checkpoint}
          onApprove={() => approveChapter1("approve")}
          onRegen={() => approveChapter1("regen")}
          onSkip={() => approveChapter1("skip")}
        />
      )}
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; color: string }> = {
    connecting:              { label: "Kết nối…",        color: "var(--muted)" },
    reconnecting:            { label: "⟳ Kết nối lại…", color: "var(--muted)" },
    navigating_plot:         { label: "Phase 1 · Plot",  color: "var(--amber)" },
    building_characters:     { label: "Phase 1 · Char",  color: "var(--amber)" },
    awaiting_plot_approval:  { label: "⏸ Plot Approval", color: "#F59E0B" },
    drafting:                { label: "Phase 2 · Draft", color: "var(--amber)" },
    awaiting_chapter1_approval: { label: "⏸ Ch.1 Approval", color: "#F59E0B" },
    completed:               { label: "✓ Hoàn thành",   color: "#4ADE80" },
    failed:                  { label: "✗ Lỗi",          color: "#F87171" },
  };
  const s = map[status] ?? { label: status, color: "var(--subtle)" };
  return (
    <span className="text-xs font-semibold uppercase tracking-wider px-3 py-1 rounded-full"
      style={{ color: s.color, background: "var(--surface)", border: `1px solid ${s.color}` }}>
      {s.label}
    </span>
  );
}

function BlueprintPanel({ blueprint, chapters }: { blueprint: BlueprintSummary; chapters: ChapterMeta[] }) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-bold mb-1" style={{ fontFamily: "var(--font-playfair)", color: "var(--heading)" }}>
          {blueprint.title}
        </h2>
        <p className="text-xs leading-relaxed" style={{ color: "var(--subtle)" }}>{blueprint.premise}</p>
      </div>

      <div>
        <p className="text-xs uppercase tracking-widest font-semibold mb-2" style={{ color: "var(--muted)" }}>Thế giới</p>
        <p className="text-xs leading-relaxed" style={{ color: "var(--subtle)" }}>{blueprint.world_summary}</p>
      </div>

      <div>
        <p className="text-xs uppercase tracking-widest font-semibold mb-2" style={{ color: "var(--muted)" }}>Chương</p>
        <div className="space-y-2">
          {blueprint.chapters.map((ch) => {
            const done = chapters.find((c) => c.number === ch.number);
            return (
              <div key={ch.number} className="text-xs px-3 py-2 rounded-sm"
                style={{ background: "var(--surface)", border: `1px solid ${done ? "var(--amber)" : "var(--border)"}` }}>
                <span style={{ color: done ? "var(--amber)" : "var(--subtle)" }}>
                  {ch.number}. {ch.title}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <div>
        <p className="text-xs uppercase tracking-widest font-semibold mb-2" style={{ color: "var(--muted)" }}>Nhân vật</p>
        <div className="space-y-2">
          {blueprint.characters.map((c) => (
            <div key={c.name} className="text-xs space-y-0.5" style={{ color: "var(--subtle)" }}>
              <div>
                <span style={{ color: "var(--body)" }}>{c.name}</span>
                <span style={{ color: "var(--muted)" }}> · {c.role}</span>
              </div>
              {c.core_value && <div style={{ color: "var(--muted)" }}>★ {c.core_value}</div>}
              {c.fear && <div style={{ color: "var(--muted)" }}>⚠ {c.fear}</div>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PlotApprovalModal({ data, onApprove, onReject }: {
  data: CheckpointPlotData;
  onApprove: () => void;
  onReject: () => void;
}) {
  const bp = data.blueprint;
  return (
    <Modal title="Duyệt cốt truyện">
      <div className="space-y-4 mb-6">
        <div>
          <p className="text-sm font-semibold mb-1" style={{ color: "var(--heading)" }}>{bp.title}</p>
          <p className="text-sm" style={{ color: "var(--subtle)" }}>{bp.premise}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-widest font-semibold mb-2" style={{ color: "var(--muted)" }}>Danh sách chương</p>
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {bp.chapters.map((ch) => (
              <div key={ch.number} className="text-sm py-1" style={{ color: "var(--subtle)" }}>
                {ch.number}. <span style={{ color: "var(--body)" }}>{ch.title}</span>
                <span style={{ color: "var(--muted)" }}> (POV: {ch.pov_character})</span>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="flex gap-3">
        <button onClick={onApprove}
          className="flex-1 py-3 rounded-sm font-bold uppercase tracking-widest text-sm"
          style={{ background: "var(--amber)", color: "var(--ink)" }}>
          Duyệt
        </button>
        <button onClick={onReject}
          className="px-6 py-3 rounded-sm font-semibold text-sm"
          style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--subtle)" }}>
          Huỷ
        </button>
      </div>
    </Modal>
  );
}

function Chapter1ApprovalModal({ data, onApprove, onRegen, onSkip }: {
  data: CheckpointChapter1Data;
  onApprove: () => void;
  onRegen: () => void;
  onSkip: () => void;
}) {
  return (
    <Modal title="Duyệt chương 1">
      <div className="mb-4 flex gap-4 text-sm">
        <span style={{ color: "var(--subtle)" }}>{data.word_count.toLocaleString()} từ</span>
        <span style={{ color: data.audit_passed ? "#4ADE80" : "#F87171" }}>
          Audit: {data.audit_passed ? "PASSED" : "FAILED"}
        </span>
      </div>
      {data.audit_notes && (
        <p className="text-xs mb-3 italic" style={{ color: "var(--muted)" }}>{data.audit_notes}</p>
      )}
      <div
        className="text-sm leading-relaxed p-4 rounded-sm mb-6 max-h-56 overflow-y-auto"
        style={{ background: "var(--ink)", border: "1px solid var(--border)", color: "var(--subtle)", fontFamily: "var(--font-playfair)" }}
      >
        {data.preview}…
      </div>
      <div className="flex gap-3">
        <button onClick={onApprove}
          className="flex-1 py-3 rounded-sm font-bold uppercase tracking-widest text-sm"
          style={{ background: "var(--amber)", color: "var(--ink)" }}>
          Duyệt
        </button>
        <button onClick={onRegen}
          className="px-5 py-3 rounded-sm font-semibold text-sm"
          style={{ background: "var(--surface)", border: "1px solid var(--amber)", color: "var(--amber)" }}>
          Viết lại
        </button>
        <button onClick={onSkip}
          className="px-5 py-3 rounded-sm font-semibold text-sm"
          style={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--subtle)" }}>
          Bỏ qua
        </button>
      </div>
    </Modal>
  );
}

function Phase1Timer({ status, elapsed }: { status: string; elapsed: number }) {
  const label = status === "navigating_plot" ? "Đang tạo cốt truyện" : "Đang xây dựng nhân vật";
  const dots = ".".repeat((elapsed % 3) + 1).padEnd(3, " ");
  return (
    <div className="mt-2 px-4 py-3 rounded-sm font-mono text-xs"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <div className="flex justify-between">
        <span style={{ color: "var(--subtle)" }}>⚙ {label}{dots}</span>
        <span style={{ color: "var(--amber)" }}>{elapsed}s</span>
      </div>
    </div>
  );
}

function ChapterProgressBar({ progress }: { progress: WritingProgress }) {
  const pct = Math.min(100, Math.round((progress.words_so_far / progress.target) * 100));
  const filled = Math.round(pct / 5);
  const bar = "█".repeat(filled) + "░".repeat(20 - filled);
  return (
    <div className="mt-2 px-4 py-3 rounded-sm font-mono text-xs"
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <div className="flex justify-between mb-2">
        <span style={{ color: "var(--subtle)" }}>
          ✍ Ch.{progress.chapter_number} · {progress.chapter_title}
        </span>
        <span style={{ color: "var(--amber)" }}>
          {progress.words_so_far.toLocaleString()} / {progress.target.toLocaleString()} từ
        </span>
      </div>
      <div className="flex items-center gap-2">
        <span style={{ color: "var(--amber)", letterSpacing: "-0.05em" }}>{bar}</span>
        <span style={{ color: "var(--muted)" }}>{pct}%</span>
      </div>
    </div>
  );
}

function Modal({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 flex items-center justify-center z-50 px-4"
      style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}>
      <div
        className="w-full max-w-lg rounded-sm p-6 fade-up"
        style={{ background: "var(--paper)", border: "1px solid var(--border)" }}
      >
        <div className="flex items-center gap-3 mb-5">
          <span className="amber-rule" />
          <h2 className="text-lg font-bold" style={{ fontFamily: "var(--font-playfair)", color: "var(--heading)" }}>
            {title}
          </h2>
        </div>
        {children}
      </div>
    </div>
  );
}
