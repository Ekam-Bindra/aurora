# AURORA Web (`apps/web`)

The AURORA executive frontend — Next.js (App Router) + TypeScript + Tailwind, using the design
system in [`docs/architecture/ui-ux-plan.md`](../../docs/architecture/ui-ux-plan.md).

## Status (Phases 1–8 merged)

All dashboard modules are wired to live API data (see
[`docs/roadmap/implementation-roadmap.md`](../../docs/roadmap/implementation-roadmap.md)):

- ✅ App shell with RBAC-aware sidebar navigation, dark-first theme (`@aurora/config/tailwind`)
- ✅ Login page (`POST /auth/login`) + token handling
- ✅ Executive dashboard with live KPIs, forecasting, risk genome, graph explorer,
  Monte Carlo simulations, AI agent chat, explain overlay
- ✅ Data sources (CSV upload + job status), board reports, admin console
- ✅ 4 Playwright E2E flows in `e2e/` (see [`docs/E2E.md`](../../docs/E2E.md))

## Develop

```bash
# from the repo root (pnpm workspace)
pnpm install
pnpm --filter @aurora/web dev      # http://localhost:3000

# point the app at the API (defaults to http://localhost/api/v1)
export NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

## Typed API client

`lib/api.ts` mixes generated and hand-rolled types:

- **Generated** — `lib/api-types.ts` is emitted by [openapi-typescript] from `openapi.json`
  (the FastAPI spec, dumped without a running server). Both files are **versioned** so the
  web build never needs Python. Generated-backed today: `AuthUser`, `LoginResponse`, and the
  `HealthResponse`/`ReadyResponse` path aliases.
- **Hand-rolled** — most GET routes (`/board-reports`, `/ingestion/jobs`, metrics, graph,
  forecasts, …) return an untyped `{data, meta}` envelope (plain `dict`, no `response_model`),
  so their generated types collapse to `Record<string, unknown>`. The interfaces in
  `lib/api.ts` remain the source of truth for those.

Regenerate after API changes (needs `apps/api/.venv`):

```bash
pnpm generate:api-types    # runs scripts/generate-api-types.sh
```

**Follow-up:** declaring typed response envelopes (`response_model`) on the FastAPI routes —
starting with health/ready, board reports, and ingestion jobs — would let the generated
schemas replace the remaining hand-rolled interfaces (and surface drift such as the client
sending a `template` field that `BoardReportCreate` does not declare).

[openapi-typescript]: https://github.com/openapi-ts/openapi-typescript

## Test

```bash
pnpm test:e2e:install   # one-time: download the Playwright chromium binary
pnpm test:e2e           # boots API (scripts/e2e-api.sh) + web, runs 4 flows
```

## Layout

```
app/
├── layout.tsx            # root layout (theme)
├── page.tsx              # redirects to /overview
├── (auth)/login/         # sign-in
└── (dashboard)/
    ├── layout.tsx        # authenticated shell + sidebar
    └── overview/         # executive dashboard (plus admin, agent, data,
                          #   financials, forecasting, graph, reports, risk,
                          #   simulations routes)
components/               # agent, explain, forecast, graph, risk, simulation
e2e/                      # Playwright specs + fixtures + auth helper
lib/api.ts                # thin API client
```
