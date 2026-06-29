# AURORA Web (`apps/web`)

The AURORA executive frontend — Next.js (App Router) + TypeScript + Tailwind, using the design
system in [`docs/architecture/ui-ux-plan.md`](../../docs/architecture/ui-ux-plan.md).

## Phase 1 status

Foundation scaffolding (see [`docs/roadmap/implementation-roadmap.md`](../../docs/roadmap/implementation-roadmap.md)):

- ✅ App shell with RBAC-aware sidebar navigation
- ✅ Dark-first theme wired to the shared design tokens (`@aurora/config/tailwind`)
- ✅ Login page (calls `POST /auth/login`) + token handling
- ✅ Executive dashboard route with placeholder KPI tiles
- ⏭️ Live data wiring (metrics, forecast, risk, simulator, agent) lands in Phases 3–6

> The KPI values on the overview page are placeholders until the Financial Intelligence engine
> is wired in Phase 3. Navigation items not yet built are marked “soon”.

## Develop

```bash
# from the repo root (pnpm workspace)
pnpm install
pnpm --filter @aurora/web dev      # http://localhost:3000

# point the app at the API (defaults to http://localhost/api/v1)
export NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

## Layout

```
app/
├── layout.tsx            # root layout (theme)
├── page.tsx              # redirects to /overview
├── (auth)/login/         # sign-in
└── (dashboard)/
    ├── layout.tsx        # authenticated shell + sidebar
    └── overview/         # executive dashboard
lib/api.ts                # thin API client (replaced by generated client in Phase 2)
```
