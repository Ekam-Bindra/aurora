# AURORA — Enterprise Decision Intelligence OS

> A living digital twin of your company that turns fragmented operational data into
> board-ready decisions. Think **Bloomberg Terminal × SAP × Palantir Foundry × an AI CFO**,
> unified into one decision-intelligence operating system.

AURORA ingests a company's financial, operational, customer, vendor, and people data;
fuses it into a single governed data model and a live knowledge graph; continuously scores
enterprise risk; forecasts the future; lets executives **simulate decisions before they make
them**; and explains every number and recommendation in plain language with traceable evidence.

---

## Why AURORA exists

Executives do not suffer from a lack of dashboards. They suffer from **fragmentation**:
finance lives in the ERP, pipeline in the CRM, headcount in the HRIS, contracts in a drive,
and the "real story" in a quarterly slide deck that is stale the moment it is presented.
No single system can answer a question like:

> *"If we lose our second-largest customer next quarter and raise pay by 6% to retain
> engineering, what happens to cash runway, gross margin, and our delivery risk — and what
> are my three best counter-moves?"*

AURORA is built to answer exactly that class of question: cross-domain, forward-looking,
quantified, explainable, and tied to concrete recommended actions.

### The four pillars

| Pillar | Analogy | What AURORA does |
|--------|---------|------------------|
| **See everything** | Bloomberg Terminal | One real-time executive surface for every key metric, signal, and trend. |
| **Model the business** | SAP / ERP | A governed, multi-tenant data model of the whole company. |
| **Connect the dots** | Palantir Foundry | A knowledge graph linking people, customers, vendors, products, contracts, and money. |
| **Advise & decide** | AI CFO / Chief of Staff | Forecasts, risk genome, decision simulation, and an explainable executive AI agent. |

---

## The 12 core modules

1. **Enterprise Data Integration Layer** — connectors, file ingestion, ETL, validation, lineage.
2. **Unified Company Data Model** — the canonical multi-tenant schema (PostgreSQL).
3. **Company Knowledge Graph** — entities and relationships in Neo4j for dependency analysis.
4. **Financial Intelligence Engine** — margins, burn, runway, variance, concentration, ROI.
5. **Forecasting Engine** — revenue/expense/cash forecasts with confidence intervals.
6. **Enterprise Risk Genome** — 8 continuously-scored risk dimensions (0–100) with drivers.
7. **Decision Simulation Engine** — Monte Carlo "what-if" scenario modeling.
8. **Executive AI Agent** — natural-language Q&A over the company (RAG + tools).
9. **Explainability Layer** — SHAP/feature-importance + evidence trails for every output.
10. **Executive Dashboard** — the Bloomberg-style command center UI.
11. **Board Report Generator** — auto-authored, narrated, exportable board packs.
12. **Enterprise Admin Console** — tenants, users, roles, data sources, audit, billing.

A detailed treatment of each module is in
[`docs/architecture/system-architecture.md`](docs/architecture/system-architecture.md).

---

## Who it is for

Eight executive and operator personas — CEO, CFO, COO, Chief Strategy Officer, Finance
Analyst, Operations Manager, Department Head, and System Administrator. Their goals,
top questions, and the permissions they get are detailed in
[`docs/00-overview-and-vision.md`](docs/00-overview-and-vision.md).

---

## Documentation index

This repository is, in its current state, a **design and architecture foundation**.
No application code ships yet; every document below is written to enough depth that an
engineering team can build from it without re-researching decisions.

### Start here
- [`docs/00-overview-and-vision.md`](docs/00-overview-and-vision.md) — product vision, personas, modules, value proposition, glossary.

### Architecture
- [`docs/architecture/system-architecture.md`](docs/architecture/system-architecture.md) — 12-module architecture, diagrams, tech-stack rationale, multi-tenancy, RBAC, data flows, infra strategy, AI provider abstraction.
- [`docs/architecture/folder-structure.md`](docs/architecture/folder-structure.md) — the monorepo layout and the responsibility of each app/package.
- [`docs/architecture/financial-risk-simulation-models.md`](docs/architecture/financial-risk-simulation-models.md) — financial formulas, forecasting methodology, the Enterprise Risk Genome, Monte Carlo simulation, and explainability.
- [`docs/architecture/ui-ux-plan.md`](docs/architecture/ui-ux-plan.md) — page inventory, dashboard layout, component plan, and design system.

### Data
- [`docs/data-model/data-model.md`](docs/data-model/data-model.md) — entity catalog, ERD, PostgreSQL DDL, Neo4j graph model, analytics layer.
- [`docs/data-model/demo-dataset-spec.md`](docs/data-model/demo-dataset-spec.md) — the "Nimbus Retail Systems" demo dataset specification.

### API
- [`docs/api/api-specification.md`](docs/api/api-specification.md) — REST endpoints per module, auth/errors/pagination, WebSocket channels, example payloads.

### Roadmap
- [`docs/roadmap/mvp-scope.md`](docs/roadmap/mvp-scope.md) — the runnable MVP slice, in/out scope, acceptance criteria.
- [`docs/roadmap/implementation-roadmap.md`](docs/roadmap/implementation-roadmap.md) — the 9 build phases with deliverables and acceptance criteria.

### Deployment
- [`docs/deployment/deployment-guide.md`](docs/deployment/deployment-guide.md) — local Docker Compose, AWS target, CI/CD, config, secrets.

---

## Target technology stack (summary)

| Layer | Technology |
|-------|------------|
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS, shadcn/ui, Recharts/Plotly, React Flow |
| Backend | Python, FastAPI, REST + WebSocket, Pydantic, SQLAlchemy |
| Relational store | PostgreSQL (multi-tenant, row-level isolation) |
| Knowledge graph | Neo4j |
| Cache / jobs | Redis + RQ/Celery |
| Analytics store | DuckDB (lean) → ClickHouse (scale) |
| Object storage | S3-compatible (MinIO locally) |
| AI / ML | Provider abstraction over OpenAI / AWS Bedrock + offline mock; LangChain/LlamaIndex; scikit-learn, XGBoost, Prophet/statsmodels; SHAP |
| Infra | Docker + Docker Compose (local), AWS ECS/RDS/S3/CloudWatch (cloud), GitHub Actions CI/CD, optional Terraform |

Rationale for each choice is in
[`docs/architecture/system-architecture.md`](docs/architecture/system-architecture.md#technology-stack-rationale).

---

## Quickstart (planned)

> ⚠️ Not yet runnable. The commands below describe the **intended** local developer
> experience once the MVP build (see [`docs/roadmap/mvp-scope.md`](docs/roadmap/mvp-scope.md))
> is implemented. The authoritative, maintained instructions live in the
> [deployment guide](docs/deployment/deployment-guide.md).

```bash
# 1. Clone and configure
git clone <repo-url> aurora && cd aurora
cp .env.example .env            # fill in AI provider keys, or leave blank to use the offline mock

# 2. Bring up the full stack (api, web, postgres, neo4j, redis, minio)
docker compose up -d

# 3. Seed the demo company "Nimbus Retail Systems"
docker compose exec api python -m aurora.seed --demo nimbus

# 4. Open the executive dashboard
open http://localhost:3000        # login: demo@nimbus.test / see seed output
```

---

## Project status

| Area | Status |
|------|--------|
| Vision & architecture docs | **In progress (this session)** |
| Data model & demo spec | **In progress (this session)** |
| API contract | **In progress (this session)** |
| Application code | Not started (designed here, built next) |
| Infrastructure code | Not started (designed here, built next) |

---

## License

To be determined before any public release. Treat all contents as proprietary for now.
