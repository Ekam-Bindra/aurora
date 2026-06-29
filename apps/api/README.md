# AURORA API (`apps/api`)

The AURORA backend — a Python/FastAPI **modular monolith**. This package implements the
server side of the platform; see [`docs/architecture/system-architecture.md`](../../docs/architecture/system-architecture.md)
for the full design and [`docs/architecture/folder-structure.md`](../../docs/architecture/folder-structure.md)
for where each module lives.

## Phase 1 status

This is the **Foundation** phase (see [`docs/roadmap/implementation-roadmap.md`](../../docs/roadmap/implementation-roadmap.md)):

- ✅ App factory, typed settings, structured logging + request-id correlation
- ✅ Consistent error envelope (`docs/api/api-specification.md` §5)
- ✅ JWT auth (`/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/me`)
- ✅ RBAC: 13 permissions, the 8 personas, and a `require_permission` guard
- ✅ Multi-tenant scoping (every read is tenant-scoped)
- ✅ Health/readiness probes
- ✅ Demo "Nimbus" tenant seeded with all 8 persona logins
- ✅ Unit/contract tests (auth, RBAC, tenant isolation, health)

The persistence layer is an **in-memory store** in Phase 1 so the API runs and is testable with
no external services. Phase 2 swaps it for SQLAlchemy/PostgreSQL behind the same repository
interface — no route changes.

## Run locally

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# run the API
uvicorn aurora.main:app --reload --port 8000
# OpenAPI docs: http://localhost:8000/api/v1/docs

# run tests
pytest
```

### Demo logins

After startup the `nimbus` tenant is seeded. Default password: `aurora-demo-2026`
(`DEMO_PASSWORD`). Users: `ceo@`, `cfo@`, `coo@`, `strategy@`, `analyst@`, `ops@`, `depthead@`,
`admin@` `nimbus.test`.

```bash
curl -s localhost:8000/api/v1/auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"cfo@nimbus.test","password":"aurora-demo-2026"}'
```

## Layout

```
aurora/
├── core/        # config, logging, errors, security, rbac, tenancy, pagination
├── domain/      # API-facing models
├── repositories/# in-memory store (Phase 1) -> SQLAlchemy (Phase 2)
├── seed/        # demo tenant seeding
├── modules/     # auth, health, workspaces (more modules per roadmap)
├── api/         # versioned router aggregation (/api/v1)
├── deps.py      # auth-context + permission-guard dependencies
└── main.py      # app factory
```
