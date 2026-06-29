# AURORA ML

Financial intelligence calculators, DuckDB marts, metric registry, and (future) forecasting/risk models.

## Phase 3 scope

- `aurora_ml.marts` — build monthly financial mart rows from tenant DB data
- `aurora_ml.financial` — margins, burn, runway, YoY deltas, concentration
- `aurora_ml.registry` — metric definitions for explainability

## Dev

```bash
pip install -e ../database
pip install -e ".[dev]"
pytest
ruff check .
```
