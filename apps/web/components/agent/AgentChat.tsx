"use client";

import Link from "next/link";
import { useCallback, useRef, useState } from "react";
import {
  sendAgentMessage,
  type AgentCitation,
  type AgentMessageResponse,
  type AgentToolUsed,
} from "@/lib/api";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: AgentCitation[];
  tools_used?: AgentToolUsed[];
};

const SUGGESTED_PROMPTS = [
  "What's our cash runway if revenue drops 15% next quarter?",
  "Which risk dimensions are most elevated right now?",
  "Simulate losing our top customer and recommend actions.",
];

function CitationChip({ citation }: { citation: AgentCitation }) {
  const label = citation.label ?? citation.ref.split("/").pop() ?? citation.type;
  const href =
    citation.type === "simulation"
      ? `/simulations`
      : citation.type === "metric"
        ? "/financials"
        : citation.type === "forecast"
          ? "/forecasting"
          : citation.type === "risk"
            ? "/risk"
            : undefined;

  if (href) {
    return (
      <Link
        href={href}
        className="rounded-full border border-brand-primary/40 bg-brand-primary/10 px-2 py-0.5 text-xs text-brand-accent hover:bg-brand-primary/20"
      >
        {citation.type}: {label}
      </Link>
    );
  }
  return (
    <span className="rounded-full border border-border bg-elevated px-2 py-0.5 text-xs text-text-muted">
      {citation.type}: {label}
    </span>
  );
}

function ToolCallCard({ tool }: { tool: AgentToolUsed }) {
  const simRef = tool.result_ref?.includes("/simulations/");
  return (
    <div className="mt-2 rounded-md border border-border bg-elevated px-3 py-2 text-xs">
      <div className="font-medium text-brand-accent">Tool: {tool.tool}</div>
      <pre className="mt-1 overflow-x-auto text-text-muted">
        {JSON.stringify(tool.args, null, 2)}
      </pre>
      {simRef && (
        <Link href="/simulations" className="mt-1 inline-block text-brand-accent hover:underline">
          View simulation results →
        </Link>
      )}
    </div>
  );
}

export default function AgentChat({
  sessionId: initialSessionId,
  compact = false,
}: {
  sessionId?: string | null;
  compact?: boolean;
}) {
  const [sessionId, setSessionId] = useState<string | null>(initialSessionId ?? null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const appendAssistant = useCallback((res: AgentMessageResponse) => {
    setSessionId(res.session_id);
    setMessages((prev) => [
      ...prev,
      {
        id: res.interaction_id,
        role: "assistant",
        content: res.answer,
        citations: res.citations,
        tools_used: res.tools_used,
      },
    ]);
  }, []);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || loading) return;

      setError(null);
      setLoading(true);
      setMessages((prev) => [
        ...prev,
        { id: `user-${Date.now()}`, role: "user", content: trimmed },
      ]);
      setInput("");

      try {
        const res = await sendAgentMessage(trimmed, sessionId);
        appendAssistant(res);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to send message");
      } finally {
        setLoading(false);
        setTimeout(() => listRef.current?.scrollTo({ top: listRef.current.scrollHeight }), 50);
      }
    },
    [loading, sessionId, appendAssistant],
  );

  return (
    <div className={`flex flex-col ${compact ? "h-64" : "min-h-[520px]"}`}>
      <div
        ref={listRef}
        className="flex-1 space-y-4 overflow-y-auto rounded-lg border border-border bg-surface p-4"
      >
        {messages.length === 0 && (
          <div className="space-y-3">
            <p className="text-sm text-text-muted">
              Ask AURORA about metrics, forecasts, risk, or run what-if simulations.
            </p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTED_PROMPTS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => send(p)}
                  className="rounded-full border border-border px-3 py-1 text-xs text-text-muted hover:border-brand-primary hover:text-brand-accent"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                msg.role === "user"
                  ? "bg-brand-primary/20 text-text-primary"
                  : "border border-border bg-elevated"
              }`}
            >
              <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
              {msg.tools_used && msg.tools_used.length > 0 && (
                <div className="mt-2 space-y-1">
                  {msg.tools_used.map((t, i) => (
                    <ToolCallCard key={`${msg.id}-tool-${i}`} tool={t} />
                  ))}
                </div>
              )}
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {msg.citations.map((c, i) => (
                    <CitationChip key={`${msg.id}-cite-${i}`} citation={c} />
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <p className="text-xs text-text-muted" aria-live="polite">
            AURORA is thinking…
          </p>
        )}
      </div>

      {error && (
        <div className="mt-2 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
          {error}
        </div>
      )}

      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask AURORA…"
          disabled={loading}
          className="flex-1 rounded-md border border-border bg-elevated px-3 py-2 text-sm placeholder:text-text-muted focus:border-brand-primary focus:outline-none"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded-md bg-brand-primary px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
