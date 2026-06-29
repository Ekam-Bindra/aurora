# AURORA Graph

Knowledge graph projection from the unified data model: sync, traversal, impact analysis.

## Phase 4 scope

- `aurora_graph.sync` — build tenant graph from SQLAlchemy session
- `aurora_graph.memory` — in-memory store (local dev without Neo4j)
- Impact, neighbors, concentration queries

Neo4j projection (`neo4j` optional extra) is planned for Docker/full-stack deployments.

## Dev

```bash
pip install -e ../database
pip install -e ".[dev]"
pytest
ruff check .
```
