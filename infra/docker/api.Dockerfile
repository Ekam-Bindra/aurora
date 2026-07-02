# AURORA API image. Build context is the repo root.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install monorepo packages (database, ml, graph, simulations, analytics, api).
COPY packages/database/pyproject.toml packages/database/README.md /tmp/database/
COPY packages/database/aurora_db /tmp/database/aurora_db
# [postgres] extra pulls psycopg — required to reach RDS; without it the
# container only speaks SQLite.
RUN pip install --upgrade pip && pip install "/tmp/database[postgres]"

COPY packages/ml/pyproject.toml packages/ml/README.md /tmp/ml/
COPY packages/ml/aurora_ml /tmp/ml/aurora_ml
RUN pip install /tmp/ml

COPY packages/graph/pyproject.toml packages/graph/README.md /tmp/graph/
COPY packages/graph/aurora_graph /tmp/graph/aurora_graph
RUN pip install /tmp/graph

COPY packages/simulations/pyproject.toml packages/simulations/README.md /tmp/simulations/
COPY packages/simulations/aurora_sim /tmp/simulations/aurora_sim
RUN pip install /tmp/simulations

COPY packages/analytics/pyproject.toml packages/analytics/README.md /tmp/analytics/
COPY packages/analytics/aurora_analytics /tmp/analytics/aurora_analytics
RUN pip install /tmp/analytics

COPY apps/api/pyproject.toml apps/api/README.md ./
COPY apps/api/aurora ./aurora
RUN pip install .

EXPOSE 8000

CMD ["uvicorn", "aurora.main:app", "--host", "0.0.0.0", "--port", "8000"]
