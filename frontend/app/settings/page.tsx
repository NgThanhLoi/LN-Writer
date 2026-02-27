"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { API } from "../lib/constants";

type Provider = "gemini" | "openai" | "ollama";

type AgentConfig = { provider: Provider; model: string };
type AgentsMap = Record<string, AgentConfig>;

const AGENT_LABELS: Record<string, string> = {
  plot_navigator:  "Plot Navigator",
  character_soul:  "Character Soul",
  draft_master:    "Draft Master",
  final_auditor:   "Final Auditor",
  summarizer:      "Summarizer",
};

const PROVIDER_DEFAULTS: Record<Provider, string> = {
  gemini: "gemini-3-flash-preview",
  openai: "gpt-4o-mini",
  ollama: "llama3",
};

export default function SettingsPage() {
  const router = useRouter();
  const [agents, setAgents] = useState<AgentsMap>({});
  const [ollamaUrl, setOllamaUrl] = useState("http://localhost:11434/v1");
  const [openaiKey, setOpenaiKey] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  useEffect(() => {
    fetch(`${API}/settings`)
      .then((r) => r.json())
      .then((data) => {
        setAgents(data.agents ?? {});
        setOllamaUrl(data.ollama_base_url ?? "http://localhost:11434/v1");
      })
      .catch(() => showToast("Không thể tải settings", false))
      .finally(() => setLoading(false));
  }, []);

  function showToast(msg: string, ok: boolean) {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  }

  function setProvider(key: string, provider: Provider) {
    setAgents((prev) => ({
      ...prev,
      [key]: { provider, model: PROVIDER_DEFAULTS[provider] },
    }));
  }

  function setModel(key: string, model: string) {
    setAgents((prev) => ({
      ...prev,
      [key]: { ...prev[key], model },
    }));
  }

  async function save() {
    setSaving(true);
    try {
      const body: Record<string, unknown> = { agents, ollama_base_url: ollamaUrl };
      if (openaiKey) body.openai_api_key = openaiKey;

      const res = await fetch(`${API}/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
      showToast("Đã lưu settings", true);
      setOpenaiKey(""); // clear after save
    } catch (e) {
      showToast(`Lỗi: ${e}`, false);
    } finally {
      setSaving(false);
    }
  }

  const needsOllama = Object.values(agents).some((a) => a.provider === "ollama");
  const needsOpenAI = Object.values(agents).some((a) => a.provider === "openai");

  return (
    <div className="min-h-screen" style={{ background: "var(--ink)", color: "var(--body)" }}>
      {/* Header */}
      <header
        className="flex items-center justify-between px-6 py-3 border-b"
        style={{ borderColor: "var(--border)", background: "var(--paper)" }}
      >
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push("/")}
            className="text-sm"
            style={{ color: "var(--muted)" }}
          >
            ← Trang chủ
          </button>
          <span className="amber-rule" style={{ width: "1rem" }} />
          <span className="text-lg font-bold" style={{ fontFamily: "var(--font-playfair)", color: "var(--heading)" }}>
            Settings
          </span>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-6 py-10 space-y-8">
        {loading ? (
          <p style={{ color: "var(--muted)" }}>Đang tải…</p>
        ) : (
          <>
            {/* Agent configs */}
            <section>
              <h2 className="text-base font-semibold mb-4 uppercase tracking-widest text-xs"
                style={{ color: "var(--muted)" }}>
                Cấu hình Model / Agent
              </h2>
              <div className="space-y-3">
                {Object.entries(AGENT_LABELS).map(([key, label]) => {
                  const cfg = agents[key] ?? { provider: "gemini" as Provider, model: "" };
                  return (
                    <div
                      key={key}
                      className="p-4 rounded-sm"
                      style={{ background: "var(--paper)", border: "1px solid var(--border)" }}
                    >
                      <p className="text-sm font-semibold mb-3" style={{ color: "var(--heading)" }}>
                        {label}
                      </p>
                      <div className="flex gap-3">
                        {/* Provider */}
                        <select
                          value={cfg.provider}
                          onChange={(e) => setProvider(key, e.target.value as Provider)}
                          className="text-sm px-3 py-2 rounded-sm"
                          style={{
                            background: "var(--surface)",
                            border: "1px solid var(--border)",
                            color: "var(--body)",
                            minWidth: "120px",
                          }}
                        >
                          <option value="gemini">Gemini</option>
                          <option value="openai">OpenAI</option>
                          <option value="ollama">Ollama</option>
                        </select>
                        {/* Model name */}
                        <input
                          type="text"
                          value={cfg.model}
                          onChange={(e) => setModel(key, e.target.value)}
                          placeholder="model name"
                          className="flex-1 text-sm px-3 py-2 rounded-sm"
                          style={{
                            background: "var(--surface)",
                            border: "1px solid var(--border)",
                            color: "var(--body)",
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            {/* Ollama URL — only if needed */}
            {needsOllama && (
              <section>
                <h2 className="text-xs font-semibold mb-3 uppercase tracking-widest"
                  style={{ color: "var(--muted)" }}>
                  Ollama Base URL
                </h2>
                <input
                  type="text"
                  value={ollamaUrl}
                  onChange={(e) => setOllamaUrl(e.target.value)}
                  className="w-full text-sm px-3 py-2 rounded-sm"
                  style={{
                    background: "var(--paper)",
                    border: "1px solid var(--border)",
                    color: "var(--body)",
                  }}
                />
              </section>
            )}

            {/* OpenAI key — only if needed */}
            {needsOpenAI && (
              <section>
                <h2 className="text-xs font-semibold mb-3 uppercase tracking-widest"
                  style={{ color: "var(--muted)" }}>
                  OpenAI API Key
                </h2>
                <input
                  type="password"
                  value={openaiKey}
                  onChange={(e) => setOpenaiKey(e.target.value)}
                  placeholder="sk-… (để trống nếu không đổi)"
                  className="w-full text-sm px-3 py-2 rounded-sm"
                  style={{
                    background: "var(--paper)",
                    border: "1px solid var(--border)",
                    color: "var(--body)",
                  }}
                />
              </section>
            )}

            {/* Save */}
            <button
              onClick={save}
              disabled={saving}
              className="w-full py-3 rounded-sm font-bold uppercase tracking-widest text-sm"
              style={{
                background: saving ? "var(--surface)" : "var(--amber)",
                color: saving ? "var(--muted)" : "var(--ink)",
                border: saving ? "1px solid var(--border)" : "none",
                cursor: saving ? "not-allowed" : "pointer",
              }}
            >
              {saving ? "Đang lưu…" : "Lưu Settings"}
            </button>
          </>
        )}
      </main>

      {/* Toast */}
      {toast && (
        <div
          className="fixed bottom-6 right-6 px-5 py-3 rounded-sm text-sm font-semibold shadow-lg"
          style={{
            background: toast.ok ? "var(--amber)" : "#F87171",
            color: toast.ok ? "var(--ink)" : "#fff",
          }}
        >
          {toast.msg}
        </div>
      )}
    </div>
  );
}
