# AURORA — Product Overview & Vision

> **Document status:** Foundational. This is the entry point for understanding *what* AURORA
> is and *why*. Architecture, data, API, and roadmap docs build on the concepts defined here.
>
> **Related:** [README](../README.md) · [System Architecture](architecture/system-architecture.md) ·
> [Data Model](data-model/data-model.md) · [MVP Scope](roadmap/mvp-scope.md)

---

## 1. Vision

**AURORA is an enterprise decision-intelligence operating system: a living digital twin of a
company that an executive team can see, question, and steer.**

Most enterprise software is built to *record* what happened (ERPs, CRMs, HRIS) or to *report*
it (BI dashboards). AURORA is built to **decide**. It closes the loop between data and action:

```
record  →  unify  →  understand  →  foresee  →  simulate  →  recommend  →  decide  →  (record)
```

The product's north star is a single sentence an executive should be able to trust:

> *"Ask AURORA anything about your company's past, present, or possible futures, and get a
> quantified, explained, board-ready answer in seconds — including what you should do about it."*

### 1.1 What makes it different

| Conventional tooling | AURORA |
|----------------------|--------|
| Siloed by function (finance vs. ops vs. people) | One cross-domain model of the whole company |
| Backward-looking dashboards | Forward-looking forecasts + risk + simulation |
| Static reports | Conversational, explainable AI agent |
| "Here is a number" | "Here is the number, *why* it is that, and *what to do*" |
| Decisions made on intuition | Decisions stress-tested with Monte Carlo before commitment |

### 1.2 Positioning statement

> For **executive teams of mid-market and growth-stage enterprises** who must make
> high-stakes decisions with incomplete, fragmented information, **AURORA** is a
> **decision-intelligence OS** that unifies company data into a live digital twin and
> provides forecasting, risk scoring, decision simulation, and an explainable AI advisor.
> Unlike BI dashboards or point ML tools, AURORA connects every domain, looks forward,
> simulates choices, and explains itself.

---

## 2. The eight target user roles

AURORA is multi-persona by design. Each role has distinct goals, signature questions, and a
permission profile. The RBAC model that enforces these permissions is specified in
[System Architecture §Security & RBAC](architecture/system-architecture.md#7-security-rbac--multi-tenancy).

| # | Role | Primary goal | Signature questions | Access profile |
|---|------|--------------|---------------------|----------------|
| 1 | **CEO** | Steer the whole company; protect growth and survival | "Are we on track? Where is the biggest risk? What's my best move?" | Full read across all modules; approve board reports |
| 2 | **CFO** | Protect cash; hit financial targets; manage risk | "What's our runway? Where is margin leaking? What if revenue drops 15%?" | Full financial read/write; simulation; board reports |
| 3 | **COO** | Keep operations efficient and resilient | "Where are the bottlenecks? Which vendors are single points of failure?" | Operations + graph + risk; limited financial detail |
| 4 | **Chief Strategy Officer** | Plan multi-quarter strategy | "Which scenario wins over 8 quarters? What are second-order effects?" | Forecasting + simulation + graph; read financials |
| 5 | **Finance Analyst** | Produce the numbers behind decisions | "Is this variance real? What's driving the forecast?" | Financial read/write; ingestion; explainability deep-dive |
| 6 | **Operations Manager** | Run a function day to day | "Is my department over budget? Which projects are at risk?" | Scoped to assigned departments/projects |
| 7 | **Department Head** | Own a department's outcomes & budget | "How is my department performing vs. plan?" | Scoped read to own department + its graph neighborhood |
| 8 | **System Administrator** | Configure tenant, users, data sources | "Who can see what? Are integrations healthy? Is the audit trail clean?" | Admin console; users/roles/sources/audit; no financial detail by default |

> **Scoping principle.** Roles 1–5 are *enterprise-wide*; roles 6–7 are *scoped* (department-
> or project-bounded via the knowledge graph and row-level filters); role 8 is *operational*
> (manages the system but is not granted business-data visibility unless explicitly assigned).

---

## 3. The 12 core modules

Each module is summarized here and specified in depth in
[System Architecture](architecture/system-architecture.md). They are grouped into four layers.

### Layer A — Foundation (get the data right)

**1. Enterprise Data Integration Layer.** Brings data in from files (CSV/XLSX), SaaS
connectors (accounting, CRM, HRIS), and APIs. Handles upload, schema mapping, validation,
deduplication, transformation (ETL), and lineage tracking. Every record knows where it came
from. Surfaces ingestion status over WebSocket.

**2. Unified Company Data Model.** The canonical relational schema (PostgreSQL) that every
other module reads from. Defines the 21 core entities (Company → AuditLog) with strict
multi-tenant isolation. The single source of truth. See [Data Model](data-model/data-model.md).

**3. Company Knowledge Graph.** A Neo4j graph mirroring relationships the relational model
can't traverse efficiently: *customer → contract → revenue*, *vendor → product → department*,
*employee → project → customer*. Powers dependency analysis, concentration risk, and
"what depends on what" queries.

### Layer B — Intelligence (understand & foresee)

**4. Financial Intelligence Engine.** Computes the financial truth: gross/net/operating
margins, burn rate, cash runway, budget variance, revenue/customer/vendor concentration,
unit economics, and ROI. All formulas are explicit in
[Financial, Risk & Simulation Models](architecture/financial-risk-simulation-models.md).

**5. Forecasting Engine.** Projects revenue, expenses, and cash forward with confidence
intervals using time-series models (Prophet/statsmodels) plus driver-based regression.
Includes backtesting and accuracy reporting so forecasts are trusted, not guessed.

**6. Enterprise Risk Genome.** The signature feature. Continuously scores **eight risk
dimensions** on a 0–100 scale — Financial, Customer-Concentration, Vendor/Supply,
Operational, Liquidity/Cash, Talent/People, Compliance, and Market — each with its drivers,
an explanation, and recommended actions. Together they form the company's "risk genome."

### Layer C — Decision (simulate & advise)

**7. Decision Simulation Engine.** Lets executives define a scenario ("lose top customer,"
"raise prices 8%," "hire 20 engineers") and runs **Monte Carlo** simulations across thousands
of trials to show the distribution of outcomes on revenue, margin, cash, and risk — not a
single fragile point estimate.

**8. Executive AI Agent.** A natural-language interface to the entire digital twin. Uses
retrieval-augmented generation over the data model + graph, and can *call tools* (run a
forecast, score a risk, launch a simulation). Answers in plain language with citations.

**9. Explainability Layer.** No black boxes. Every metric links to its formula and inputs;
every ML output (forecast, risk score, recommendation) carries SHAP/feature-importance
attributions and an evidence trail. This is what makes outputs *board-defensible*.

### Layer D — Experience (see, report, administer)

**10. Executive Dashboard.** The Bloomberg-style command center: KPIs, trends, the risk
genome, alerts, and the AI agent, laid out for at-a-glance situational awareness. See
[UI/UX Plan](architecture/ui-ux-plan.md).

**11. Board Report Generator.** Assembles a narrated, exportable board pack (PDF/slides) from
live data: financial summary, forecast, risk genome, key decisions and their simulations —
authored by the AI agent and reviewable before sending.

**12. Enterprise Admin Console.** Manages tenants/workspaces, users, roles & permissions,
connected data sources, the audit log, and (later) billing/usage. The control plane.

---

## 4. How a decision flows through AURORA (end-to-end example)

A concrete walk-through of the "lose-a-customer" question from the README:

1. **Integration** has already ingested invoices, contracts, payroll, and the customer list.
2. **Data Model** holds the canonical records; **Knowledge Graph** knows that *Customer C2*
   is linked to 3 contracts, 18% of revenue, and 2 dependent projects.
3. The CFO asks the **AI Agent** the question in natural language.
4. The agent calls the **Simulation Engine** with a scenario: remove C2's revenue, apply a 6%
   eng-payroll increase; it runs 10,000 Monte Carlo trials.
5. The **Financial Engine** recomputes margin/runway per trial; the **Risk Genome** re-scores
   liquidity, concentration, and delivery risk.
6. The **Explainability Layer** attributes the runway change to its drivers.
7. The agent returns: the outcome distribution, the new risk genome, and **three ranked
   recommendations** ("renegotiate C2 retention," "stagger the raise," "open a credit line").
8. The CFO clicks **"Add to board report,"** and the **Board Report Generator** drops the
   narrated scenario into the next pack.

This loop — *ask → simulate → quantify → explain → recommend → report* — is the product.

---

## 5. Value proposition

### By outcome
- **Faster decisions:** minutes from question to quantified, explained answer.
- **Safer decisions:** stress-tested with simulation before commitment.
- **Earlier warnings:** continuous risk scoring surfaces problems before they hit the P&L.
- **Aligned leadership:** one shared, trustworthy version of the truth across the C-suite.
- **Less busywork:** board reports and analyses that took days are assembled in seconds.

### By persona (selected)
- **CEO:** a single situational-awareness surface + a strategist on call.
- **CFO:** runway/margin protection, variance hunting, and scenario planning in one place.
- **COO:** dependency and bottleneck visibility via the graph.
- **Strategy:** multi-quarter simulation with second-order effects.
- **Analyst:** the heavy lifting (forecasts, attributions) automated and explainable.

---

## 6. Design principles

1. **Explainable by default.** If AURORA can't show its work, it doesn't show the number.
2. **Forward-looking.** Every backward metric pairs with a forecast and a risk read.
3. **Cross-domain first.** The value is in connecting finance, ops, customers, vendors, people.
4. **Decision-oriented.** Outputs end in recommended *actions*, not just charts.
5. **Multi-tenant & secure from day one.** Isolation and RBAC are foundational, not bolted on.
6. **Lean-first, scale-ready.** Run on a laptop with Docker Compose; grow into AWS without
   re-architecting (DuckDB→ClickHouse, Compose→ECS).
7. **Provider-agnostic AI.** A thin abstraction over OpenAI/Bedrock with an **offline mock**
   so the system is fully developable and demoable without external API keys.

---

## 7. Scope of the current documentation session

This session produces the **design foundation only** — no runnable code. The artifacts are
the documents listed in the [README index](../README.md#documentation-index). Implementation
begins from [`docs/roadmap/mvp-scope.md`](roadmap/mvp-scope.md) in a later session.

---

## 8. Glossary

| Term | Definition |
|------|------------|
| **Digital twin** | A continuously-updated software model of the real company, used to observe and simulate it. |
| **Decision intelligence** | The discipline of turning data into decisions, combining analytics, forecasting, simulation, and recommendation. |
| **Tenant / Workspace** | An isolated company instance within AURORA. All data is scoped to a tenant. |
| **Unified Company Data Model** | The canonical PostgreSQL schema of 21 core entities shared by all modules. |
| **Knowledge Graph** | The Neo4j graph of entities and relationships used for dependency/concentration analysis. |
| **Enterprise Risk Genome** | AURORA's set of 8 continuously-scored risk dimensions (0–100) that together characterize a company's risk profile. |
| **Risk dimension / score** | One of the 8 genome axes (e.g., Liquidity), each with inputs, a 0–100 score, an explanation, and recommended actions. |
| **Forecast** | A model-generated projection of a metric over time, with confidence intervals. |
| **Scenario** | A user-defined set of assumptions/changes to simulate (e.g., "lose top customer"). |
| **Simulation (Monte Carlo)** | Running a scenario across many randomized trials to produce a distribution of outcomes. |
| **SimulationResult** | The stored output distribution and summary statistics of a simulation run. |
| **Recommendation** | A ranked, actionable suggestion produced by the engines/agent, with rationale. |
| **Explainability** | The layer providing formulas, inputs, SHAP/feature-importance, and evidence for any output. |
| **SHAP** | SHapley Additive exPlanations — a method to attribute a model output to its input features. |
| **Executive AI Agent** | The natural-language, tool-using assistant over the digital twin (RAG + tools). |
| **RAG** | Retrieval-Augmented Generation — grounding an LLM's answers in retrieved company data. |
| **Provider abstraction** | The interface that lets AURORA swap OpenAI/Bedrock/mock AI providers without code changes. |
| **Concentration risk** | Over-reliance on a few customers/vendors/products; a key graph-derived risk. |
| **Burn rate / Runway** | Net cash consumed per month / months of cash remaining at current burn. |
| **Lineage** | The recorded origin and transformation history of each ingested record. |
| **Board pack / report** | The exportable executive/board document AURORA assembles from live data. |
| **RBAC** | Role-Based Access Control — permissions granted by role and scope. |
| **Audit log** | Immutable record of significant actions for compliance and traceability. |

---

## 9. Where to go next

- Understand the system → [System Architecture](architecture/system-architecture.md)
- Understand the data → [Data Model](data-model/data-model.md) and [Demo Dataset](data-model/demo-dataset-spec.md)
- Understand the math → [Financial, Risk & Simulation Models](architecture/financial-risk-simulation-models.md)
- Understand the build order → [MVP Scope](roadmap/mvp-scope.md) → [Implementation Roadmap](roadmap/implementation-roadmap.md)
