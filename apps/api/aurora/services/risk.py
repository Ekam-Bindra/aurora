"""Risk genome service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from aurora_ml.financial import FinancialEngine
from aurora_ml.marts import get_mart_rows
from aurora_ml.risk import RiskGenomeEngine
from sqlalchemy.orm import Session

from .graph import graph_concentration

_genome_cache: Dict[str, Dict[str, Any]] = {}
_history: Dict[str, List[Dict[str, Any]]] = {}


def compute_genome(session: Session, company_id: str) -> Dict[str, Any]:
    rows = get_mart_rows(session, company_id)
    fin = FinancialEngine(rows)
    conc = graph_concentration(company_id)
    engine = RiskGenomeEngine(
        fin,
        customer_concentration=conc.get("customers"),
        vendor_concentration=conc.get("vendors"),
    )
    payload = engine.to_dict(engine.compute())
    _genome_cache[company_id] = payload
    hist = _history.setdefault(company_id, [])
    hist.append({"computed_at": payload["computed_at"], "overall_score": payload["overall_score"]})
    if len(hist) > 52:
        _history[company_id] = hist[-52:]
    return payload


def get_genome(company_id: str) -> Optional[Dict[str, Any]]:
    return _genome_cache.get(company_id)


def get_dimension(company_id: str, dimension: str) -> Optional[Dict[str, Any]]:
    genome = _genome_cache.get(company_id)
    if not genome:
        return None
    for d in genome.get("dimensions", []):
        if d.get("dimension") == dimension:
            return d
    return None


def genome_history(company_id: str) -> List[Dict[str, Any]]:
    return list(_history.get(company_id, []))
