/**
 * Minimal typed API client for the AURORA backend.
 *
 * Phase 1 hand-rolls a thin wrapper; Phase 2 replaces this with the generated client in
 * `packages/types` (OpenAPI -> TS), per docs/architecture/folder-structure.md.
 */

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  (typeof window !== "undefined" ? "/api/v1" : "http://localhost:8000/api/v1");
const TOKEN_KEY = "aurora.access_token";

export type AuthUser = {
  id: string;
  full_name: string;
  email: string;
  title: string;
  company: { id: string; name: string; slug: string };
  roles: string[];
  permissions: string[];
};

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      message = body?.error?.message ?? message;
    } catch {
      /* non-JSON error */
    }
    throw new Error(message);
  }
  return (await res.json()) as T;
}

export async function login(email: string, password: string): Promise<AuthUser> {
  const data = await request<{ access_token: string; user: AuthUser }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setToken(data.access_token);
  return data.user;
}

export async function getMe(): Promise<AuthUser> {
  return request<AuthUser>("/auth/me");
}

export type MetricKpiMoney = {
  value_cents: number;
  currency: string;
  delta_pct_yoy?: number | null;
};

export type MetricKpiRatio = {
  value: number | null;
  delta_pct_yoy?: number | null;
};

export type MetricsOverviewData = {
  as_of: string | null;
  kpis: {
    revenue_mtd?: MetricKpiMoney;
    gross_margin?: MetricKpiRatio;
    operating_margin?: MetricKpiRatio;
    net_burn?: { value_cents: number; currency: string };
    cash_runway_months?: { value: number; trend?: string };
  };
};

export type MetricSeriesPoint = {
  period: string;
  value?: number;
  value_cents?: number;
};

export type PnlSummary = {
  from: string;
  to: string;
  revenue_cents: number;
  cogs_cents: number;
  gross_profit_cents: number;
  expenses_cents: number;
  net_profit_cents: number;
  currency: string;
};

export type CashSummary = {
  cash_cents: number;
  net_burn_cents: number;
  runway_months: number | null;
  currency: string;
  as_of: string;
};

export type ConcentrationEntry = {
  name: string;
  amount_cents: number;
  share: number;
};

export type ConcentrationData = {
  customers: {
    top_5_share: number;
    hhi_normalized: number;
    top: ConcentrationEntry[];
  };
  vendors: {
    top_5_share: number;
    hhi_normalized: number;
    top: ConcentrationEntry[];
  };
};

export async function getMetricsOverview(): Promise<MetricsOverviewData> {
  const res = await request<{ data: MetricsOverviewData }>("/metrics/overview");
  return res.data;
}

export async function getMetricSeries(metric: string): Promise<MetricSeriesPoint[]> {
  const res = await request<{ data: { points: MetricSeriesPoint[] } }>(
    `/metrics/${metric}/series`,
  );
  return res.data.points;
}

export async function getPnlSummary(from: string, to: string): Promise<PnlSummary> {
  const res = await request<{ data: PnlSummary }>(
    `/financials/pnl?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
  );
  return res.data;
}

export async function getCashSummary(): Promise<CashSummary> {
  const res = await request<{ data: CashSummary }>("/financials/cash");
  return res.data;
}

export async function getConcentration(): Promise<ConcentrationData> {
  const res = await request<{ data: ConcentrationData }>("/metrics/concentration");
  return res.data;
}

export type GraphNode = {
  id: string;
  label: string;
  name: string;
  criticality?: string;
  line?: string;
};

export type GraphImpact = {
  node: GraphNode | null;
  impact: {
    affected_products: GraphNode[];
    affected_customers: Array<GraphNode & { revenue_share?: number; amount_cents?: number }>;
    affected_departments: GraphNode[];
    affected_employees: GraphNode[];
    estimated_revenue_at_risk_cents: number;
  };
};

export async function getGraphNodes(label?: string): Promise<GraphNode[]> {
  const q = label ? `?label=${encodeURIComponent(label)}` : "";
  const res = await request<{ data: { nodes: GraphNode[] } }>(`/graph/nodes${q}`);
  return res.data.nodes;
}

export async function getGraphImpact(nodeId: string, depth = 2): Promise<GraphImpact> {
  const res = await request<{ data: GraphImpact }>(
    `/graph/impact/${encodeURIComponent(nodeId)}?depth=${depth}`,
  );
  return res.data;
}

export type GraphEdge = {
  id?: string;
  source_id: string;
  target_id: string;
  type: string;
  properties?: Record<string, unknown>;
};

export type GraphNeighborhood = {
  node: GraphNode | null;
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export async function getGraphNeighbors(nodeId: string, depth = 2): Promise<GraphNeighborhood> {
  const res = await request<{ data: GraphNeighborhood }>(
    `/graph/neighbors/${encodeURIComponent(nodeId)}?depth=${depth}`,
  );
  return res.data;
}

export function formatCents(cents: number, compact = true): string {
  const dollars = cents / 100;
  if (compact && Math.abs(dollars) >= 1_000_000) {
    return `$${(dollars / 1_000_000).toFixed(1)}M`;
  }
  if (compact && Math.abs(dollars) >= 1_000) {
    return `$${(dollars / 1_000).toFixed(1)}K`;
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(dollars);
}

export function formatPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatYoY(delta: number | null | undefined): string | undefined {
  if (delta === null || delta === undefined) return undefined;
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toFixed(1)}% YoY`;
}

// --- Forecasting (Phase 5) ---

export type ForecastPoint = {
  period: string;
  yhat_cents: number;
  lower_cents: number;
  upper_cents: number;
};

export type ForecastAccuracy = {
  mape: number;
  rmse_cents: number;
  backtest_windows: number;
  interval_coverage?: number | null;
};

export type ForecastData = {
  id: string;
  metric: string;
  method: string;
  horizon_periods: number;
  status: string;
  points: ForecastPoint[];
  accuracy?: ForecastAccuracy | null;
  model_version?: string;
  explain_ref?: string;
};

export type ForecastCreateParams = {
  metric?: string;
  granularity?: string;
  horizon_periods?: number;
  method?: string;
};

export async function listForecasts(): Promise<ForecastData[]> {
  const res = await request<{ data: { forecasts: ForecastData[] } }>("/forecasts");
  return res.data.forecasts;
}

export async function getForecast(forecastId: string): Promise<ForecastData> {
  const res = await request<{ data: ForecastData }>(`/forecasts/${encodeURIComponent(forecastId)}`);
  return res.data;
}

export async function createForecast(params: ForecastCreateParams = {}): Promise<{ id: string; status: string }> {
  const res = await request<{ data: { id: string; status: string } }>("/forecasts", {
    method: "POST",
    body: JSON.stringify({
      metric: params.metric ?? "revenue",
      granularity: params.granularity ?? "month",
      horizon_periods: params.horizon_periods ?? 12,
      method: params.method ?? "baseline",
    }),
  });
  return res.data;
}

// --- Risk Genome (Phase 5) ---

export type RiskDriver = {
  factor: string;
  value: number;
  contribution: number;
};

export type RiskDimension = {
  dimension: string;
  score: number;
  severity: "low" | "moderate" | "high" | "critical" | string;
  drivers: RiskDriver[];
  explanation: string;
  recommended_actions: string[];
};

export type RiskGenomeData = {
  computed_at: string;
  overall_score: number;
  dimensions: RiskDimension[];
};

export type RiskGenomeHistoryEntry = {
  computed_at: string;
  overall_score: number;
};

export async function getRiskGenome(): Promise<RiskGenomeData> {
  const res = await request<{ data: RiskGenomeData }>("/risk/genome");
  return res.data;
}

export async function getRiskDimension(dimension: string): Promise<RiskDimension> {
  const res = await request<{ data: RiskDimension }>(
    `/risk/genome/${encodeURIComponent(dimension)}`,
  );
  return res.data;
}

export async function getRiskGenomeHistory(): Promise<RiskGenomeHistoryEntry[]> {
  const res = await request<{ data: { history: RiskGenomeHistoryEntry[] } }>("/risk/genome/history");
  return res.data.history;
}

export function formatDimensionLabel(key: string): string {
  return key
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function severityTone(severity: string): "positive" | "warning" | "negative" | "muted" {
  switch (severity) {
    case "low":
      return "positive";
    case "moderate":
      return "warning";
    case "high":
      return "warning";
    case "critical":
      return "negative";
    default:
      return "muted";
  }
}

// --- Scenarios & Simulations (Phase 6) ---

export type ShockType = "customer_churn" | "expense_change";

export type CustomerChurnShock = {
  type: "customer_churn";
  customer_id: string;
  probability?: number;
};

export type ExpenseChangeShock = {
  type: "expense_change";
  category: string;
  department_code?: string;
  pct_change: number;
};

export type ScenarioShock = CustomerChurnShock | ExpenseChangeShock;

export type ScenarioCreateParams = {
  name: string;
  horizon_periods?: number;
  trials?: number;
  assumptions: {
    shocks: ScenarioShock[];
    distributions?: Record<string, { dist: string; mean: number; std?: number }>;
  };
};

export type ScenarioData = {
  id: string;
  name: string;
  status: string;
  horizon_periods: number;
  trials: number;
  assumptions: ScenarioCreateParams["assumptions"];
  simulation_id?: string | null;
};

export type SimulationMetricSummary = {
  mean: number;
  p5: number;
  p50: number;
  p95: number;
  prob_below_3?: number;
};

export type SimulationResultMetric = {
  metric: string;
  summary: SimulationMetricSummary;
  histogram?: number[];
};

export type SimulationRecommendation = {
  title: string;
  priority: number;
  expected_impact?: {
    metric: string;
    direction: string;
    magnitude: string;
  };
};

export type SimulationData = {
  id: string;
  scenario_id: string;
  status: string;
  trials: number;
  results: SimulationResultMetric[];
  risk_deltas: Record<string, number>;
  recommendations: SimulationRecommendation[];
  explain_ref?: string;
};

export type SimulationRunResponse = {
  simulation_id: string;
  status: string;
  ws_channel?: string;
};

export async function listScenarios(): Promise<ScenarioData[]> {
  const res = await request<{ data: { scenarios: ScenarioData[] } }>("/scenarios");
  return res.data.scenarios;
}

export async function createScenario(params: ScenarioCreateParams): Promise<{ id: string; status: string }> {
  const res = await request<{ data: { id: string; status: string } }>("/scenarios", {
    method: "POST",
    body: JSON.stringify({
      name: params.name,
      horizon_periods: params.horizon_periods ?? 12,
      trials: params.trials ?? 10000,
      assumptions: params.assumptions,
    }),
  });
  return res.data;
}

export async function getScenario(scenarioId: string): Promise<ScenarioData> {
  const res = await request<{ data: ScenarioData }>(`/scenarios/${encodeURIComponent(scenarioId)}`);
  return res.data;
}

export async function runScenario(scenarioId: string): Promise<SimulationRunResponse> {
  const res = await request<{ data: SimulationRunResponse }>(
    `/scenarios/${encodeURIComponent(scenarioId)}/run`,
    { method: "POST" },
  );
  return res.data;
}

export async function getSimulation(simulationId: string): Promise<SimulationData> {
  const res = await request<{ data: SimulationData }>(
    `/simulations/${encodeURIComponent(simulationId)}`,
  );
  return res.data;
}

export function formatMetricLabel(key: string): string {
  return key
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

// --- AI Agent (Phase 6) ---

export type AgentCitation = {
  type: "metric" | "simulation" | "forecast" | "risk" | string;
  ref: string;
  label?: string;
};

export type AgentToolUsed = {
  tool: string;
  args: Record<string, unknown>;
  result_ref?: string;
};

export type AgentMessageResponse = {
  session_id: string;
  interaction_id: string;
  answer: string;
  tools_used: AgentToolUsed[];
  citations: AgentCitation[];
  provider: string;
  model: string;
  tokens?: { input: number; output: number };
};

export type AgentSession = {
  id: string;
  title?: string;
  created_at: string;
  message_count?: number;
};

export type AgentSessionMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: AgentCitation[];
  tools_used?: AgentToolUsed[];
  created_at?: string;
};

export async function sendAgentMessage(
  message: string,
  sessionId?: string | null,
): Promise<AgentMessageResponse> {
  const res = await request<{ data: AgentMessageResponse }>("/agent/messages", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId ?? null, message }),
  });
  return res.data;
}

export async function listAgentSessions(): Promise<AgentSession[]> {
  const res = await request<{ data: { sessions: AgentSession[] } }>("/agent/sessions");
  return res.data.sessions;
}

export async function getAgentSession(sessionId: string): Promise<{
  session: AgentSession;
  messages: AgentSessionMessage[];
}> {
  const res = await request<{
    data: { session: AgentSession; messages: AgentSessionMessage[] };
  }>(`/agent/sessions/${encodeURIComponent(sessionId)}`);
  return res.data;
}

// --- Explainability (Phase 6) ---

export type ExplainEvidence = { type: string; ref: string };

export type ExplainFeature = { feature: string; importance: number };

export type ExplainInput = { name: string; value: string | number; source?: string };

export type ExplainData = {
  ref: string;
  kind: "metric" | "forecast" | "risk" | "simulation";
  title: string;
  formula?: string;
  method?: string;
  narrative?: string;
  inputs?: ExplainInput[];
  feature_importance?: ExplainFeature[];
  drivers?: RiskDriver[];
  backtest?: { windows: number; mape: number; coverage_80pct?: number };
  evidence?: ExplainEvidence[];
};

function parseExplainRef(ref: string): { kind: ExplainData["kind"]; id: string } | null {
  const cleaned = ref.replace(/^\/api\/v1/, "").replace(/^\//, "");
  const metricMatch = cleaned.match(/^explain\/metric\/([^?]+)/);
  if (metricMatch?.[1]) return { kind: "metric", id: metricMatch[1] };
  const forecastMatch = cleaned.match(/^explain\/forecast\/([^/?]+)/);
  if (forecastMatch?.[1]) return { kind: "forecast", id: forecastMatch[1] };
  const riskMatch = cleaned.match(/^explain\/risk\/([^/?]+)/);
  if (riskMatch?.[1]) return { kind: "risk", id: riskMatch[1] };
  const simMatch = cleaned.match(/^explain\/simulation\/([^/?]+)/);
  if (simMatch?.[1]) return { kind: "simulation", id: simMatch[1] };
  return null;
}

export async function getExplain(ref: string): Promise<ExplainData> {
  const parsed = parseExplainRef(ref);
  if (!parsed) throw new Error(`Unsupported explain ref: ${ref}`);

  const path = `/explain/${parsed.kind}/${encodeURIComponent(parsed.id)}`;
  const res = await request<{ data: Record<string, unknown> }>(path);
  const raw = res.data;

  const title =
    (raw.title as string) ??
    (raw.metric as string) ??
    (raw.forecast_id as string) ??
    (raw.signal_id as string) ??
    parsed.id;

  return {
    ref,
    kind: parsed.kind,
    title: typeof title === "string" ? formatMetricLabel(title.replace(/^fc_/, "")) : parsed.id,
    formula: raw.formula as string | undefined,
    method: raw.method as string | undefined,
    narrative: raw.narrative as string | undefined,
    inputs: raw.inputs as ExplainInput[] | undefined,
    feature_importance: raw.feature_importance as ExplainFeature[] | undefined,
    drivers: raw.drivers as RiskDriver[] | undefined,
    backtest: raw.backtest as ExplainData["backtest"],
    evidence: raw.evidence as ExplainEvidence[] | undefined,
  };
}
