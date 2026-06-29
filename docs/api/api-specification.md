# AURORA — API Specification

> **Document status:** Foundational contract for `apps/api`. The OpenAPI document this spec
> describes is the source of truth that generates the typed frontend client
> ([`packages/types`](../architecture/folder-structure.md#43-packagestypes--shared-typescript-types--api-client)).
>
> **Related:** [System Architecture](../architecture/system-architecture.md) ·
> [Data Model](../data-model/data-model.md) ·
> [Financial, Risk & Simulation Models](../architecture/financial-risk-simulation-models.md) ·
> [UI/UX Plan](../architecture/ui-ux-plan.md)

---

## 1. Conventions

| Topic | Convention |
|-------|------------|
| Base URL | `/api/v1` (versioned; breaking changes bump the version) |
| Format | JSON only (`Content-Type: application/json`); UTF-8 |
| Money | Integer **minor units** + `currency` (e.g., `{"amount_cents": 4500000, "currency":"USD"}`) |
| Timestamps | ISO-8601 UTC (`2026-06-28T21:00:00Z`) |
| IDs | UUID strings (except `audit_log.id` which is a numeric string) |
| Naming | `snake_case` field names; plural resource paths |
| Idempotency | Mutating POSTs accept an `Idempotency-Key` header |
| Tenancy | Tenant derived from the auth token; never passed in the URL |
| Tracing | Every response includes `X-Request-Id`; echo it in bug reports |

---

## 2. Authentication & authorization

### 2.1 Scheme
- **Bearer JWT** access tokens in `Authorization: Bearer <token>` (short-lived, ~15 min).
- **Refresh tokens** (HTTP-only cookie or secure store) exchange for new access tokens.
- Tokens carry `user_id`, `tenant_id` (`company_id`), `roles`, and resolved `scopes`.
- Authorization is enforced per-endpoint via required permissions; see the matrix in
  [Architecture §7.2](../architecture/system-architecture.md#72-authorization-rbac). Each
  endpoint below lists its **required permission**.

### 2.2 Auth endpoints

| Method | Path | Permission | Description |
|--------|------|-----------|-------------|
| POST | `/api/v1/auth/login` | public | Exchange credentials for tokens |
| POST | `/api/v1/auth/refresh` | public (valid refresh) | New access token |
| POST | `/api/v1/auth/logout` | authenticated | Revoke refresh token |
| GET | `/api/v1/auth/me` | authenticated | Current user, roles, scopes, tenant |

**`POST /auth/login`**

```jsonc
// Request
{ "email": "cfo@nimbus.test", "password": "••••••••" }

// 200 OK
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {
    "id": "8f1c...e2", "full_name": "Marcus Lin", "email": "cfo@nimbus.test",
    "title": "Chief Financial Officer",
    "company": { "id": "a3...91", "name": "Nimbus Retail Systems", "slug": "nimbus" },
    "roles": ["CFO"],
    "permissions": ["read:financials","write:financials","run:simulation","use:ai_agent","create:board_report","approve:board_report"]
  }
}
```

---

## 3. Standard envelopes

### 3.1 Single resource
```jsonc
{ "data": { /* resource object */ }, "meta": { "request_id": "req_01H..." } }
```

### 3.2 Collection (paginated)
```jsonc
{
  "data": [ /* items */ ],
  "pagination": { "page": 1, "page_size": 50, "total_items": 312, "total_pages": 7,
                  "next_cursor": "eyJpZCI6...", "prev_cursor": null },
  "meta": { "request_id": "req_01H..." }
}
```

---

## 4. Pagination, filtering, sorting

| Param | Example | Notes |
|-------|---------|-------|
| `page`, `page_size` | `?page=2&page_size=50` | offset pagination (default 50, max 200) |
| `cursor` | `?cursor=eyJ...` | cursor pagination for large/append-only sets (audit, AI logs) |
| `sort` | `?sort=-issue_date` | `-` prefix = descending; comma-separated for multi-sort |
| filters | `?status=overdue&customer_id=...&from=2026-01-01&to=2026-03-31` | per-resource documented filters; dates are inclusive |
| `q` | `?q=continental` | free-text search where supported (trigram on names) |

---

## 5. Error model

All errors share one envelope and use appropriate HTTP status codes.

```jsonc
{
  "error": {
    "code": "validation_error",         // stable machine-readable code
    "message": "Invoice total must be >= 0.",
    "details": [                          // optional, field-level
      { "field": "total_cents", "issue": "must be >= 0" }
    ],
    "request_id": "req_01H..."
  }
}
```

| HTTP | `code` | When |
|------|--------|------|
| 400 | `validation_error` | malformed/invalid input |
| 401 | `unauthorized` | missing/invalid/expired token |
| 403 | `forbidden` | authenticated but lacks permission/scope |
| 404 | `not_found` | resource absent or not in tenant |
| 409 | `conflict` | uniqueness/version conflict |
| 422 | `unprocessable` | semantically invalid (e.g., bad scenario assumptions) |
| 429 | `rate_limited` | too many requests (includes `Retry-After`) |
| 500 | `internal_error` | unexpected; never leaks internals |
| 503 | `ai_provider_unavailable` | LLM provider down (agent falls back to mock if configured) |

> **Tenant safety:** a resource in another tenant returns `404`, never `403`, to avoid
> confirming existence across tenants.

---

## 6. Endpoints by module

> Legend: 🔒 = required permission. Collection endpoints support §4 params unless noted.

### 6.1 Workspaces & users (Module 12 — Admin)

| Method | Path | 🔒 | Description |
|--------|------|----|-------------|
| GET | `/workspaces/current` | authenticated | Current workspace settings |
| PATCH | `/workspaces/current` | `manage:workspace` | Update settings (fiscal year, currency) |
| GET | `/users` | `manage:users` | List users |
| POST | `/users` | `manage:users` | Invite/create user |
| PATCH | `/users/{id}` | `manage:users` | Update user / deactivate |
| GET | `/roles` | `manage:users` | List roles + permissions |
| POST | `/users/{id}/roles` | `manage:users` | Assign a role (with scope) |
| DELETE | `/users/{id}/roles/{role_id}` | `manage:users` | Remove a role assignment |
| GET | `/audit-logs` | `view:audit_log` | Cursor-paginated audit trail |

### 6.2 Data integration (Module 1 — Ingestion)

| Method | Path | 🔒 | Description |
|--------|------|----|-------------|
| GET | `/data-sources` | `manage:data_sources` | List sources + health |
| POST | `/data-sources` | `manage:data_sources` | Register a source (file/connector) |
| POST | `/ingestion/uploads` | `manage:data_sources` | Upload a file (multipart) → returns job |
| POST | `/ingestion/{source_id}/sync` | `manage:data_sources` | Trigger a connector sync |
| GET | `/ingestion/jobs/{job_id}` | `manage:data_sources` | Job status, counts, errors, lineage |
| GET | `/ingestion/jobs` | `manage:data_sources` | List recent jobs |

**`POST /ingestion/uploads`** (multipart: `file`, `target` e.g. `invoices`, optional `mapping`)

```jsonc
// 202 Accepted
{ "data": { "job_id": "job_7a...", "status": "queued", "target": "invoices",
            "ws_channel": "ingestion:job_7a..." },
  "meta": { "request_id": "req_..." } }
```

**`GET /ingestion/jobs/{job_id}`**

```jsonc
// 200 OK
{ "data": {
    "job_id": "job_7a...", "status": "completed", "target": "invoices",
    "rows_total": 20000, "rows_inserted": 19880, "rows_updated": 60, "rows_rejected": 60,
    "errors": [ { "row": 1423, "issue": "unknown customer 'XYZ'", "action": "rejected" } ],
    "lineage_ref": "upload:invoices_2026q1.csv#sha256:ab12...",
    "started_at": "2026-06-28T20:55:00Z", "finished_at": "2026-06-28T20:56:12Z"
} }
```

### 6.3 Dashboard & financial metrics (Module 4)

| Method | Path | 🔒 | Description |
|--------|------|----|-------------|
| GET | `/metrics/overview` | `read:financials` | KPI snapshot for the dashboard |
| GET | `/metrics/{metric}/series` | `read:financials` | Time series for one metric |
| GET | `/metrics/concentration` | `read:financials` | Customer/vendor/product concentration |
| GET | `/financials/pnl` | `read:financials` | P&L summary for a period |
| GET | `/financials/cash` | `read:financials` | Cash balance, burn, runway |

Formulas behind every value: [Models §2](../architecture/financial-risk-simulation-models.md#2-financial-intelligence-formulas).

**`GET /metrics/overview`**

```jsonc
// 200 OK
{ "data": {
    "as_of": "2026-06-01",
    "kpis": {
      "revenue_mtd":      { "value_cents": 5120000000, "currency":"USD", "delta_pct_yoy": 17.4 },
      "gross_margin":     { "value": 0.412, "delta_pct_yoy": 2.1 },
      "operating_margin": { "value": 0.089, "delta_pct_yoy": -1.3 },
      "net_burn":         { "value_cents": -420000000, "currency":"USD" },
      "cash_runway_months": { "value": 5.4, "trend": "down" }
    },
    "explain_ref": "/explain/metric/overview?as_of=2026-06-01"
} }
```

**`GET /metrics/{metric}/series?from=2024-01-01&to=2026-06-01&granularity=month`**

```jsonc
// 200 OK  (metric=revenue)
{ "data": {
    "metric": "revenue", "granularity": "month", "currency": "USD",
    "points": [
      { "period": "2026-04-01", "value_cents": 4180000000 },
      { "period": "2026-05-01", "value_cents": 4530000000 },
      { "period": "2026-06-01", "value_cents": 5120000000 }
    ]
} }
```

### 6.4 Knowledge graph (Module 3)

| Method | Path | 🔒 | Description |
|--------|------|----|-------------|
| GET | `/graph/nodes` | `read:graph` | Nodes by label/filter (for React Flow) |
| GET | `/graph/neighbors/{node_id}` | `read:graph` | 1–N hop neighborhood |
| GET | `/graph/impact/{node_id}` | `read:graph` | Impact analysis (what depends on this) |
| GET | `/graph/concentration` | `read:graph` | Graph-derived concentration metrics |

**`GET /graph/impact/{node_id}?depth=2`** (node = critical vendor)

```jsonc
// 200 OK
{ "data": {
    "node": { "id":"v_van...", "label":"Vendor", "name":"Vanguard Freight Co.", "criticality":"critical" },
    "impact": {
      "affected_products":  [ { "id":"p_el...", "name":"Electronics Accessories" } ],
      "affected_customers": [ { "id":"c_cmg...", "name":"Continental Mercantile Group", "revenue_share": 0.14 } ],
      "affected_departments": [ { "id":"d_scm...", "name":"Supply Chain" } ],
      "estimated_revenue_at_risk_cents": 7100000000
    }
} }
```

### 6.5 Forecasting (Module 5)

| Method | Path | 🔒 | Description |
|--------|------|----|-------------|
| POST | `/forecasts` | `run:forecast` | Create a forecast (async) |
| GET | `/forecasts/{id}` | `read:financials` | Retrieve a forecast + accuracy |
| GET | `/forecasts` | `read:financials` | List forecasts |

**`POST /forecasts`**

```jsonc
// Request
{ "metric": "revenue", "granularity": "month", "horizon_periods": 12,
  "method": "ensemble", "assumptions": { "growth_override_pct": null } }

// 202 Accepted → poll GET /forecasts/{id}
{ "data": { "id": "fc_31...", "status": "queued" } }
```

**`GET /forecasts/{id}`**

```jsonc
// 200 OK
{ "data": {
    "id": "fc_31...", "metric": "revenue", "method": "ensemble", "horizon_periods": 12,
    "points": [
      { "period": "2026-07-01", "yhat_cents": 4900000000, "lower_cents": 4500000000, "upper_cents": 5300000000 },
      { "period": "2026-08-01", "yhat_cents": 5050000000, "lower_cents": 4600000000, "upper_cents": 5500000000 }
    ],
    "accuracy": { "mape": 6.8, "rmse_cents": 240000000, "backtest_windows": 6 },
    "explain_ref": "/explain/forecast/fc_31...",
    "model_version": "forecast-2026.06"
} }
```

### 6.6 Risk Genome (Module 6)

| Method | Path | 🔒 | Description |
|--------|------|----|-------------|
| GET | `/risk/genome` | `read:financials` or `read:operations` | Current 8-dimension genome |
| GET | `/risk/genome/{dimension}` | (as above) | One dimension w/ drivers + actions |
| GET | `/risk/genome/history` | (as above) | Score history per dimension |
| POST | `/risk/recompute` | `run:forecast` | Force a recompute (async) |

**`GET /risk/genome`**

```jsonc
// 200 OK
{ "data": {
    "computed_at": "2026-06-28T06:00:00Z",
    "overall_score": 58.2,
    "dimensions": [
      { "dimension":"liquidity", "score":74.0, "severity":"high",
        "drivers":[ {"factor":"cash_runway_months","value":5.4,"contribution":0.46} ],
        "explanation":"Runway fell below 6 months due to a Q expense spike and slower collections.",
        "recommended_actions":[ "Open a $5M revolving credit line", "Tighten AR terms to net-30" ] },
      { "dimension":"customer_concentration", "score":66.0, "severity":"high",
        "drivers":[ {"factor":"top_customer_share","value":0.14,"contribution":0.51} ],
        "explanation":"Top customer is 14% of revenue and trending up.",
        "recommended_actions":[ "Diversify pipeline", "Negotiate a multi-year retention contract" ] }
      // ... 6 more dimensions
    ]
} }
```

### 6.7 Decision simulation (Module 7)

| Method | Path | 🔒 | Description |
|--------|------|----|-------------|
| POST | `/scenarios` | `run:simulation` | Create a scenario |
| GET | `/scenarios/{id}` | `run:simulation` | Scenario + status |
| POST | `/scenarios/{id}/run` | `run:simulation` | Launch Monte Carlo (async) |
| GET | `/simulations/{id}` | `run:simulation` | Results (distributions, risk deltas, recos) |
| GET | `/scenarios` | `run:simulation` | List scenarios |

**`POST /scenarios`** — assumption schema in [Models §5](../architecture/financial-risk-simulation-models.md#5-decision-simulation-engine-monte-carlo).

```jsonc
// Request
{ "name": "Lose top customer + 6% eng raise",
  "horizon_periods": 12, "trials": 10000,
  "assumptions": {
    "shocks": [
      { "type": "customer_churn", "customer_id": "c_cmg...", "probability": 1.0 },
      { "type": "expense_change", "category": "payroll", "department_code": "ENG",
        "pct_change": 0.06 }
    ],
    "distributions": { "revenue_growth_pct": { "dist": "normal", "mean": 0.015, "std": 0.02 } }
  } }

// 201 Created
{ "data": { "id": "sc_aa...", "status": "draft" } }
```

**`POST /scenarios/{id}/run`**

```jsonc
// 202 Accepted
{ "data": { "simulation_id": "sim_aa...", "status": "queued",
            "ws_channel": "simulation:sim_aa..." } }
```

**`GET /simulations/{id}`**

```jsonc
// 200 OK
{ "data": {
    "id": "sim_aa...", "scenario_id": "sc_aa...", "status": "completed", "trials": 10000,
    "results": [
      { "metric": "cash_runway_months",
        "summary": { "mean": 3.1, "p5": 1.4, "p50": 3.0, "p95": 5.2, "prob_below_3": 0.48 } },
      { "metric": "gross_margin",
        "summary": { "mean": 0.40, "p5": 0.37, "p50": 0.40, "p95": 0.43 } }
    ],
    "risk_deltas": { "liquidity": +14.0, "customer_concentration": -9.0, "operational": +6.0 },
    "recommendations": [
      { "title": "Open a revolving credit line before Q4", "priority": 1,
        "expected_impact": { "metric":"cash_runway_months","direction":"up","magnitude":"+2.5mo" } },
      { "title": "Stage the engineering raise over two quarters", "priority": 2 },
      { "title": "Lock a 24-month retention deal with the top customer", "priority": 2 }
    ],
    "explain_ref": "/explain/simulation/sim_aa..."
} }
```

### 6.8 Executive AI agent (Module 8)

| Method | Path | 🔒 | Description |
|--------|------|----|-------------|
| POST | `/agent/messages` | `use:ai_agent` | Ask a question (may call tools) |
| GET | `/agent/sessions/{id}` | `use:ai_agent` | Conversation history |
| GET | `/agent/sessions` | `use:ai_agent` | List sessions |

**`POST /agent/messages`**

```jsonc
// Request
{ "session_id": null,
  "message": "What's our cash runway if revenue drops 15% next quarter, and what should we do?" }

// 200 OK
{ "data": {
    "session_id": "se_77...", "interaction_id": "ai_77...",
    "answer": "At a 15% revenue drop, projected cash runway falls to ~3.0 months (p50; p5 ≈ 1.4). The main driver is reduced collections against fixed payroll. Top actions: (1) open a $5M credit line, (2) defer non-critical Q4 marketing, (3) accelerate AR. See the simulation for the full distribution.",
    "tools_used": [
      { "tool": "run_simulation", "args": { "shock":"revenue_-15%" }, "result_ref": "/simulations/sim_bb..." }
    ],
    "citations": [
      { "type":"metric", "ref":"/metrics/cash" },
      { "type":"simulation", "ref":"/simulations/sim_bb..." }
    ],
    "provider": "mock", "model": "aurora-mock-1", "tokens": { "input": 1840, "output": 320 }
} }
```

> If no AI key is configured, `provider` is `mock` and answers are deterministic — the endpoint
> never fails for lack of a provider. See
> [Architecture §8](../architecture/system-architecture.md#8-ai-provider-abstraction).

### 6.9 Board reports (Module 11)

| Method | Path | 🔒 | Description |
|--------|------|----|-------------|
| POST | `/board-reports` | `create:board_report` | Create a report (sections selected) |
| POST | `/board-reports/{id}/generate` | `create:board_report` | Narrate + render (async) |
| GET | `/board-reports/{id}` | `read:financials` | Report content + status |
| POST | `/board-reports/{id}/approve` | `approve:board_report` | Approve |
| GET | `/board-reports/{id}/export` | `read:financials` | Signed URL to rendered PDF |
| GET | `/board-reports` | `read:financials` | List reports |

**`POST /board-reports`**

```jsonc
// Request
{ "title": "Q2 2026 Board Pack", "period_start": "2026-04-01", "period_end": "2026-06-30",
  "sections": ["financial_summary","forecast","risk_genome","key_decisions"] }
// 201 Created
{ "data": { "id": "br_q2...", "status": "draft" } }
```

### 6.10 Explainability (Module 9, cross-cutting)

| Method | Path | 🔒 | Description |
|--------|------|----|-------------|
| GET | `/explain/metric/{metric}` | inherits metric perm | Formula, inputs, values for a metric |
| GET | `/explain/forecast/{id}` | `read:financials` | Feature importance + backtest detail |
| GET | `/explain/risk/{signal_id}` | inherits risk perm | Driver attribution + evidence |
| GET | `/explain/simulation/{id}` | `run:simulation` | Outcome driver attribution |

**`GET /explain/forecast/{id}`**

```jsonc
// 200 OK
{ "data": {
    "forecast_id": "fc_31...",
    "method": "ensemble (prophet + sarimax + driver-regression)",
    "feature_importance": [
      { "feature": "seasonality_q4", "importance": 0.38 },
      { "feature": "trend",          "importance": 0.31 },
      { "feature": "marketing_spend_lag1", "importance": 0.14 }
    ],
    "backtest": { "windows": 6, "mape": 6.8, "coverage_80pct": 0.81 },
    "evidence": [ { "type":"series","ref":"/metrics/revenue/series" } ]
} }
```

---

## 7. WebSocket channels

Real-time progress is delivered over WebSocket, authenticated with the same bearer token
(passed as a query param or first message). Channels are tenant-scoped server-side.

**Connect:** `wss://<host>/api/v1/ws?token=<jwt>` then subscribe to channels.

| Channel | Emitted by | Purpose |
|---------|-----------|---------|
| `ingestion:{job_id}` | Module 1 worker | ETL progress & completion |
| `simulation:{simulation_id}` | Module 7 worker | Monte Carlo progress & completion |
| `forecast:{forecast_id}` | Module 5 worker | Forecast job progress |
| `report:{report_id}` | Module 11 worker | Narration/render progress |
| `risk:genome` | Module 6 | Push when the genome is recomputed |

**Message envelope**

```jsonc
{ "channel": "simulation:sim_aa...", "event": "progress",
  "data": { "pct": 62, "trials_done": 6200, "trials_total": 10000 },
  "ts": "2026-06-28T21:01:10Z" }
```

```jsonc
{ "channel": "simulation:sim_aa...", "event": "completed",
  "data": { "simulation_id": "sim_aa...", "result_url": "/api/v1/simulations/sim_aa..." },
  "ts": "2026-06-28T21:01:30Z" }
```

```jsonc
{ "channel": "ingestion:job_7a...", "event": "progress",
  "data": { "pct": 50, "stage": "validating", "rows_processed": 10000 },
  "ts": "2026-06-28T20:55:40Z" }
```

`event` values: `progress` | `completed` | `failed` (failed includes an `error` object using the
§5 error shape).

---

## 8. Rate limiting & quotas
- Default: 600 requests/min per user; AI agent and simulation endpoints have lower, separate
  buckets (compute-heavy). `429` responses include `Retry-After` and
  `X-RateLimit-{Limit,Remaining,Reset}` headers.

## 9. Versioning & compatibility
- URI-versioned (`/api/v1`). Additive changes (new fields/endpoints) are non-breaking.
- Breaking changes ship under `/api/v2` with an overlap/deprecation window.
- The OpenAPI doc is published at `/api/v1/openapi.json` and drives
  [`packages/types`](../architecture/folder-structure.md#43-packagestypes--shared-typescript-types--api-client).

---

## 10. Endpoint summary (by module)

| Module | Base paths |
|--------|-----------|
| Auth/Workspaces/Admin (12) | `/auth/*`, `/workspaces/*`, `/users/*`, `/roles/*`, `/audit-logs` |
| Ingestion (1) | `/data-sources/*`, `/ingestion/*` |
| Financial metrics (4) | `/metrics/*`, `/financials/*` |
| Graph (3) | `/graph/*` |
| Forecasting (5) | `/forecasts/*` |
| Risk (6) | `/risk/*` |
| Simulation (7) | `/scenarios/*`, `/simulations/*` |
| AI Agent (8) | `/agent/*` |
| Board Reports (11) | `/board-reports/*` |
| Explainability (9) | `/explain/*` |

---

## 11. Where to go next
- The objects these endpoints return → [Data Model](../data-model/data-model.md)
- The math behind metrics/forecasts/risk/simulation → [Financial, Risk & Simulation Models](../architecture/financial-risk-simulation-models.md)
- How the UI consumes these → [UI/UX Plan](../architecture/ui-ux-plan.md)
- What ships in the MVP subset → [MVP Scope](../roadmap/mvp-scope.md)
