"use client";

import AgentChat from "@/components/agent/AgentChat";

export default function AgentPage() {
  return (
    <div className="p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">AI Agent</h1>
        <p className="text-sm text-text-muted">
          Grounded executive assistant — answers cite metrics, forecasts, risk signals, and
          simulations. Tool calls are shown inline.
        </p>
      </header>

      <AgentChat />
    </div>
  );
}
