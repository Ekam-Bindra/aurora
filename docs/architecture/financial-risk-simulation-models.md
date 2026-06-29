# AURORA — Financial, Risk & Simulation Models

> **Document status:** Foundational quantitative reference. Every metric, forecast, risk score,
> simulation, and explanation in AURORA is defined here with its **formula, inputs, and output
> range**, so implementation needs no further research.
>
> **Related:** [System Architecture](system-architecture.md) ·
> [Data Model](../data-model/data-model.md) · [API Specification](../api/api-specification.md) ·
> [Demo Dataset](../data-model/demo-dataset-spec.md)

---

## 1. Conventions

- Periods are months unless noted; \( t \) indexes the current month, \( t-1 \) the prior.
- Monetary inputs come from the analytics marts
  ([Data Model §6](../data-model/data-model.md#6-analytics-layer-duckdb--clickhouse)); shown as
  decimals here, stored as integer cents.
- Every computed value carries a `model_version` and the inputs used, for the
  [explainability layer §6](#6-explainability-layer).
- Notation: \( R \) = revenue, \( \text{COGS} \) = cost of goods sold, \( \text{OpEx} \) =
  operating expenses, \( C \) = cash balance.

---

## 2. Financial intelligence formulas

### 2.1 Margins

\[
\text{Gross Profit}_t = R_t - \text{COGS}_t
\qquad
\text{Gross Margin}_t = \frac{R_t - \text{COGS}_t}{R_t}
\]

\[
\text{Operating Margin}_t = \frac{R_t - \text{COGS}_t - \text{OpEx}_t}{R_t}
\qquad
\text{Net Margin}_t = \frac{\text{Net Income}_t}{R_t}
\]

where \( \text{Net Income}_t = R_t - \text{COGS}_t - \text{OpEx}_t - \text{Interest}_t - \text{Tax}_t \).

- **Range:** ratios typically \( (-\infty, 1] \); displayed as %. Guard \( R_t > 0 \) (else `null`).

### 2.2 Burn rate & cash runway

Net burn is the average monthly cash decrease over a trailing window \( k \) (default \( k=3 \)):

\[
\text{Net Burn}_t = \frac{1}{k}\sum_{i=0}^{k-1}\big(\text{Cash Outflow}_{t-i} - \text{Cash Inflow}_{t-i}\big)
\]

Equivalently \( \text{Net Burn}_t = -\frac{1}{k}\sum (C_{t-i} - C_{t-i-1}) \). A positive value
means cash is being consumed.

\[
\text{Cash Runway}_t \;(\text{months}) =
\begin{cases}
\dfrac{C_t}{\text{Net Burn}_t} & \text{if } \text{Net Burn}_t > 0 \\[2mm]
\infty \;(\text{"profitable"}) & \text{if } \text{Net Burn}_t \le 0
\end{cases}
\]

- **Inputs:** `cash` series, inflows (collections), outflows (expenses+payroll).
- **Range:** \( [0, \infty) \) months. This is the headline number behind the **Liquidity** risk.

### 2.3 Budget variance

For a department/category with budget \( B \) and actual \( A \) in period \( t \):

\[
\text{Variance}_t = A_t - B_t
\qquad
\text{Variance \%}_t = \frac{A_t - B_t}{B_t}
\]

- Positive variance on expenses = overspend. Flagged when \( |\text{Variance \%}| > \tau \)
  (default \( \tau = 0.10 \)).

### 2.4 Concentration (Herfindahl–Hirschman Index)

Given shares \( s_i = x_i / \sum_j x_j \) across \( n \) customers (or vendors/products):

\[
\text{HHI} = \sum_{i=1}^{n} s_i^{2} \in \left[\tfrac{1}{n}, 1\right]
\qquad
\text{Top-}k\text{ Share} = \sum_{i=1}^{k} s_{(i)}
\]

where \( s_{(i)} \) are shares sorted descending.

- **Interpretation:** HHI near \( 1/n \) = diversified; near \( 1 \) = highly concentrated.
- Normalized for scoring: \( \text{HHI}^{*} = \dfrac{\text{HHI} - 1/n}{1 - 1/n} \in [0,1] \).
- Feeds the **Customer-Concentration** and **Vendor/Supply** risk dimensions; computed both in
  SQL marts and the [graph](../data-model/data-model.md#53-example-cypher-concentration--impact).

### 2.5 Unit economics & ROI

\[
\text{Contribution Margin}_p = \text{Price}_p - \text{Unit Cost}_p
\qquad
\text{ARPC} = \frac{R}{\#\,\text{active customers}}
\]

\[
\text{ROI} = \frac{\text{Gain} - \text{Cost}}{\text{Cost}}
\qquad
\text{Project ROI}_t = \frac{\text{Value Delivered}_t - \text{Spent}_t}{\text{Spent}_t}
\]

Optional CAC/LTV when marketing + retention data exist:
\( \text{LTV} \approx \text{ARPC} \times \text{Gross Margin} \times \bar{T} \) (avg lifetime
\( \bar T \) months), \( \text{LTV/CAC} \) as an efficiency ratio.

### 2.6 Growth & trend

\[
\text{MoM Growth}_t = \frac{R_t - R_{t-1}}{R_{t-1}}
\qquad
\text{YoY Growth}_t = \frac{R_t - R_{t-12}}{R_{t-12}}
\]

- Smoothed trend uses a trailing 3-month moving average to suppress monthly noise.

### 2.7 Metric registry
Each metric is registered as `(id, formula_version, inputs[], output_range, unit)` so the API's
`/explain/metric/{metric}` ([API §6.10](../api/api-specification.md#610-explainability-module-9-cross-cutting))
can return the exact computation. Adding/altering a metric bumps its `formula_version`.

---

## 3. Forecasting methodology

### 3.1 Objective
Project `revenue`, `expenses`, and `cash` (and derived `net_burn`, `runway`) forward 1–24 months
with **calibrated confidence intervals** and reported accuracy.

### 3.2 Models (ensemble)
AURORA forecasts each metric with up to three complementary models, then blends them.

1. **Prophet** — captures trend + multiplicative yearly seasonality (the strong Q4 retail peak
   in the [demo data](../data-model/demo-dataset-spec.md#4-financial-shape-trend-seasonality--targets)).
   Decomposition: \( y(t) = g(t) + s(t) + h(t) + \varepsilon_t \) (trend + seasonality + holidays).
2. **SARIMAX** (statsmodels) — \( \text{SARIMA}(p,d,q)(P,D,Q)_{12} \) for autocorrelated series;
   exogenous regressors (e.g., marketing spend) supported.
3. **Driver regression** — gradient-boosted or linear model on engineered features
   (lags, moving averages, seasonal dummies, marketing lag, headcount) for interpretability and
   the [feature-importance explanation](#6-explainability-layer).

**Ensemble:** inverse-error weighting from backtests,
\[
\hat y_t^{\text{ens}} = \sum_m w_m \,\hat y_t^{(m)},\qquad
w_m = \frac{1/\text{MAPE}_m}{\sum_{m'} 1/\text{MAPE}_{m'}} .
\]

### 3.3 Confidence intervals
- Prophet/SARIMAX provide native predictive intervals.
- For the ensemble/regression, intervals come from backtest residual quantiles (or conformal
  prediction): the 80% interval is \( [\hat y_t + q_{0.10},\ \hat y_t + q_{0.90}] \) using the
  empirical residual distribution. Reported as `lower`/`upper` in the
  [forecast payload](../api/api-specification.md#65-forecasting-module-5).

### 3.4 Evaluation (backtesting)
- **Rolling-origin** cross-validation: expand the train window, forecast the next horizon,
  slide forward (default 6 windows).
- **Metrics:**
\[
\text{MAPE} = \frac{100}{N}\sum_t \left|\frac{y_t - \hat y_t}{y_t}\right|,\quad
\text{RMSE} = \sqrt{\frac{1}{N}\sum_t (y_t-\hat y_t)^2},\quad
\text{MAE} = \frac{1}{N}\sum_t |y_t-\hat y_t|.
\]
- **Interval calibration:** empirical coverage of the 80% interval should be ≈ 0.80.
- Accuracy is stored on the `Forecast` record and surfaced in
  [`/explain/forecast/{id}`](../api/api-specification.md#610-explainability-module-9-cross-cutting).

### 3.5 Cold start & guardrails
- < 12 months of history → fall back to trend + simple seasonal naïve; flag low confidence.
- Forecasts are clipped to sane bounds (no negative revenue) and annotated when assumptions
  override the model (e.g., a user-supplied growth rate).

---

## 4. The Enterprise Risk Genome

The signature feature: **8 risk dimensions**, each continuously scored on **0–100** (higher =
more risk), each with **inputs, a normalized score, a severity band, drivers, an explanation,
and recommended actions**. Together they are the company's "risk genome."

### 4.1 Scoring framework

Each dimension \( d \) computes one or more **sub-factors** \( f_j \), normalizes each to
\( [0,1] \), and combines them with weights \( w_j \) (\( \sum_j w_j = 1 \)):

\[
\text{Score}_d = 100 \times \sum_j w_j \cdot \phi_j(f_j)
\]

**Normalizers** \( \phi_j \) map a raw factor to \( [0,1] \) (higher = riskier):

- *Threshold-linear* (e.g., runway): \( \phi = \operatorname{clip}\!\big(\tfrac{T_{\max}-x}{T_{\max}-T_{\min}},0,1\big) \).
- *Direct ratio* (e.g., normalized HHI, variance %): \( \phi = \operatorname{clip}(x,0,1) \).
- *Logistic* for soft thresholds: \( \phi = \dfrac{1}{1+e^{-k(x-x_0)}} \).

**Severity bands** (applied to every score):

| Score | Severity |
|-------|----------|
| 0–25 | low |
| 26–50 | moderate |
| 51–75 | high |
| 76–100 | critical |

**Overall genome score:** a weighted blend (defaults below; configurable per tenant):

\[
\text{Overall} = \sum_d \omega_d \cdot \text{Score}_d .
\]

### 4.2 The eight dimensions

| # | Dimension | Primary inputs | Key sub-factors → normalizer | Default \( \omega_d \) |
|---|-----------|----------------|------------------------------|:----------------------:|
| 1 | **Financial** | margins, net income trend | gross-margin decline, operating-margin level, earnings volatility | 0.16 |
| 2 | **Customer Concentration** | revenue by customer | normalized HHI, top-customer share, top-10 share | 0.13 |
| 3 | **Vendor / Supply** | spend by vendor, criticality, graph | normalized spend HHI, critical single-points-of-failure, delivery reliability | 0.12 |
| 4 | **Operational** | projects, budget variance, throughput | red-project ratio, budget-variance %, dependency centrality | 0.12 |
| 5 | **Liquidity / Cash** | cash, burn, runway, AR aging | runway (threshold-linear), burn trend, overdue-AR ratio | 0.18 |
| 6 | **Talent / People** | attrition, key-person allocation | attrition rate, key-person concentration (graph), open-critical-roles | 0.10 |
| 7 | **Compliance** | contracts, audit, expiries | expiring/expired critical contracts, missing approvals, audit findings | 0.09 |
| 8 | **Market** | growth vs. trend, external shocks | revenue-vs-expectation gap, demand volatility, concentration of revenue by region | 0.10 |

### 4.3 Worked example — Liquidity (dimension 5)

Sub-factors and weights:

| Sub-factor \( f_j \) | Raw value (demo) | Normalizer \( \phi_j \) | \( \phi_j \) | \( w_j \) |
|----------------------|------------------|--------------------------|:-----------:|:--------:|
| Cash runway (months) | 5.4 | threshold-linear, \( T_{\min}=3, T_{\max}=18 \): \( \tfrac{18-5.4}{18-3} \) | 0.84 | 0.55 |
| Burn trend (3-mo Δ) | +18% | logistic around 0 | 0.66 | 0.25 |
| Overdue-AR ratio | 0.11 | direct ratio (cap 0.30→1): \( 0.11/0.30 \) | 0.37 | 0.20 |

\[
\text{Score}_{\text{liquidity}} = 100\,(0.55\cdot0.84 + 0.25\cdot0.66 + 0.20\cdot0.37) = 100\,(0.462+0.165+0.074) \approx 70.1
\]

→ **score ≈ 70 → "high"**, matching the demo's engineered liquidity squeeze
([anomaly C](../data-model/demo-dataset-spec.md#5-injected-anomalies-for-detection--explainability)).
Drivers are ranked by \( w_j\phi_j \) (runway dominates), producing:

```jsonc
{ "dimension":"liquidity", "score":70.1, "severity":"high",
  "drivers":[
    {"factor":"cash_runway_months","value":5.4,"contribution":0.66},
    {"factor":"burn_trend_pct","value":0.18,"contribution":0.24},
    {"factor":"overdue_ar_ratio","value":0.11,"contribution":0.10}],
  "explanation":"Runway is 5.4 months (below the 6-month threshold) with rising burn; the dominant driver is low runway.",
  "recommended_actions":["Open a $5M revolving credit line","Tighten AR terms to net-30","Defer non-critical Q4 spend"] }
```

### 4.4 Recommended actions
Each dimension maps its top drivers to a curated **action library** (driver → candidate actions,
with expected impact). The [AI agent](system-architecture.md#module-8--executive-ai-agent) can
expand these into prose and the [Board Report Generator](system-architecture.md#module-11--board-report-generator)
into narrated recommendations. Actions persist as
[`recommendation`](../data-model/data-model.md#4-postgresql-ddl) rows.

### 4.5 Cadence & history
- Recomputed on schedule (e.g., nightly) and on demand
  ([`POST /risk/recompute`](../api/api-specification.md#66-risk-genome-module-6)); each run
  appends `risk_signal` rows so trends (e.g., concentration creep) are visible over time.

---

## 5. Decision Simulation Engine (Monte Carlo)

### 5.1 Concept
A **scenario** perturbs the baseline (forecasts + current financial state) with **deterministic
shocks** and **uncertain assumptions**, then runs \( N \) trials (default 10,000) to produce a
**distribution** of outcomes — not a single fragile estimate.

### 5.2 Scenario assumption schema
(Mirrors the [API scenario payload](../api/api-specification.md#67-decision-simulation-module-7).)

| Element | Meaning | Example |
|---------|---------|---------|
| `shocks[]` | deterministic structural changes | `customer_churn` (remove a customer's revenue), `expense_change` (+6% ENG payroll), `price_change`, `vendor_failure` |
| `distributions{}` | uncertain drivers sampled per trial | `revenue_growth_pct ~ Normal(0.015, 0.02)`, `cogs_inflation ~ Triangular(...)` |
| `correlations` (opt.) | dependence between drivers | growth ↔ collections |
| `horizon_periods` | months simulated | 12 |
| `trials` | Monte Carlo iterations | 10000 |

Supported sampling distributions: Normal, LogNormal, Triangular, Uniform, Bernoulli (for
event shocks), and empirical (bootstrap from history).

### 5.3 Algorithm

```text
for trial in 1..N:
    draw uncertain drivers ~ specified distributions (respecting correlations)
    apply deterministic shocks to the baseline (revenue, costs, customers, vendors)
    for month in 1..H:
        project revenue/expenses (baseline forecast × drivers ± shocks)
        recompute financial metrics  (Section 2)  -> margin, burn, cash, runway
        recompute affected risk scores (Section 4) -> liquidity, concentration, operational
        propagate graph dependency effects (e.g., vendor_failure -> product -> customer revenue)
    record per-trial outcome vector (metrics @ horizon + min runway, etc.)
aggregate across trials -> distributions + summary stats + risk deltas
```

Implementation is **vectorized** (NumPy): trials are array dimensions, so 10k×12 runs complete
in well under a second for the demo. Heavy runs execute as
[async jobs with WebSocket progress](../api/api-specification.md#7-websocket-channels).

### 5.4 Outputs
For each tracked metric, the engine reports the distribution and summary statistics:

\[
\text{mean},\ \text{std},\ p_5,\ p_{50},\ p_{95},\ \Pr[X < \theta]
\]

(e.g., \( \Pr[\text{runway} < 3\ \text{months}] \)), plus **risk deltas** (change in each genome
dimension vs. baseline) and **ranked recommendations**. Stored as
[`simulation_result`](../data-model/data-model.md#4-postgresql-ddl).

### 5.5 Graph-coupled effects
Structural shocks traverse the [knowledge graph](../data-model/data-model.md#5-neo4j-knowledge-graph-model):
a `vendor_failure` on the critical logistics vendor follows
`SUPPLIES → Product → PURCHASED ← Customer` to estimate revenue-at-risk, then
`DELIVERS_FOR → Project → WORKS_ON → Employee` for operational/talent impact — exactly the
[demo dependency chain](../data-model/demo-dataset-spec.md#6-dependency-relationships-for-the-knowledge-graph--simulation).

### 5.6 Validation
- **Reproducibility:** each run records its seed, `model_version`, and assumptions.
- **Sanity bounds:** a zero-shock scenario must reproduce the baseline forecast (regression test).
- **Convergence:** report Monte Carlo standard error \( \approx \sigma/\sqrt{N} \); auto-increase
  trials if key percentiles haven't stabilized.

---

## 6. Explainability layer

No output ships without an explanation. Three complementary mechanisms:

### 6.1 Deterministic (metrics)
Every financial metric returns its **formula, inputs, and intermediate values** from the
[metric registry §2.7](#27-metric-registry) — fully transparent, no ML needed.

### 6.2 Feature attribution (ML outputs)
For forecasts, ML-based risk sub-factors, and recommendations, AURORA uses **SHAP** (model-
agnostic Shapley values):

\[
\hat f(x) = \phi_0 + \sum_{j=1}^{M} \phi_j,\qquad
\phi_j = \text{contribution of feature } j .
\]

- Local explanations: per-forecast/per-score feature contributions (waterfall).
- Global explanations: mean \( |\phi_j| \) across the dataset → the `feature_importance` array in
  [`/explain/forecast/{id}`](../api/api-specification.md#610-explainability-module-9-cross-cutting).
- For linear/regression drivers, standardized coefficients corroborate SHAP.

### 6.3 Risk driver attribution
Risk scores are **additive by construction** (§4.1), so each driver's contribution is exactly
\( w_j\phi_j \) — already interpretable, returned ranked in
[`/explain/risk/{signal_id}`](../api/api-specification.md#610-explainability-module-9-cross-cutting).

### 6.4 Evidence trails
Every explanation links back to the **source records and lineage**
([Data Model §7](../data-model/data-model.md#7-data-lifecycle--integrity)): which invoices,
expenses, or graph nodes drove the number — what makes outputs board-defensible.

### 6.5 Simulation attribution
Outcome variance is attributed to assumptions via variance decomposition / Sobol-style
sensitivity (which driver moved runway most), returned in
[`/explain/simulation/{id}`](../api/api-specification.md#610-explainability-module-9-cross-cutting).

---

## 7. Model governance
- **Versioning:** metrics (`formula_version`), forecasts/risk/sim (`model_version`) stored with
  every output; changing a formula/model never silently rewrites history.
- **Reproducibility:** inputs + seeds + versions persisted → any number can be regenerated.
- **Testing:** unit tests per formula/scorer (golden values on the demo dataset), backtests for
  forecasts, and zero-shock regression for simulation.
- **Configurability:** thresholds (\( \tau \), runway bounds), weights (\( w_j, \omega_d \)), and
  trial counts are tenant-configurable with sane defaults documented here.

---

## 8. Where to go next
- The data these models consume → [Data Model](../data-model/data-model.md) & [Demo Dataset](../data-model/demo-dataset-spec.md)
- How outputs are exposed → [API Specification](../api/api-specification.md)
- How they're visualized → [UI/UX Plan](ui-ux-plan.md)
- When each engine is built → [Implementation Roadmap](../roadmap/implementation-roadmap.md)
