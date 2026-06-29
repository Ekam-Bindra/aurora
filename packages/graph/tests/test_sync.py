"""Graph sync and impact tests."""

from aurora_db.base import Base
from aurora_db.seed.nimbus import CRITICAL_VENDOR, KEY_PROJECT, TOP_CUSTOMER, seed_nimbus
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aurora_graph.memory import InMemoryGraphStore
from aurora_graph.sync import ELECTRONICS_LINE, sync_company_graph


def _seeded_store(scale: float = 0.05):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    result = seed_nimbus(session, seed=42, scale=scale, password="test")
    session.commit()
    company_id = result["company_id"]
    snapshot = sync_company_graph(session, company_id)
    store = InMemoryGraphStore()
    store.replace(snapshot)
    return session, company_id, store


def test_sync_and_vendor_impact():
    session, company_id, store = _seeded_store()
    vendors = store.list_nodes(company_id, label="Vendor")
    critical = next(v for v in vendors if v["name"] == CRITICAL_VENDOR)
    impact = store.impact(company_id, critical["id"], depth=2, session=session)

    assert impact["node"]["name"] == CRITICAL_VENDOR
    products = impact["impact"]["affected_products"]
    assert len(products) > 0
    customers = impact["impact"]["affected_customers"]
    assert len(customers) > 0
    assert impact["impact"]["estimated_revenue_at_risk_cents"] > 0


def test_vanguard_impact_chain_golden():
    """Validate the demo dependency chain from demo-dataset-spec.md §6."""
    session, company_id, store = _seeded_store()
    vendors = store.list_nodes(company_id, label="Vendor")
    critical = next(v for v in vendors if v["name"] == CRITICAL_VENDOR)
    impact = store.impact(company_id, critical["id"], depth=3, session=session)

    assert critical["criticality"] == "critical"

    products = impact["impact"]["affected_products"]
    electronics = [p for p in products if p.get("line") == ELECTRONICS_LINE]
    assert len(electronics) >= 1
    assert all(ELECTRONICS_LINE in p["name"] for p in electronics)

    customer_names = {c["name"] for c in impact["impact"]["affected_customers"]}
    assert TOP_CUSTOMER in customer_names

    continental = next(
        c for c in impact["impact"]["affected_customers"] if c["name"] == TOP_CUSTOMER
    )
    assert 0.10 <= continental["revenue_share"] <= 0.20

    dept_names = {d["name"] for d in impact["impact"]["affected_departments"]}
    assert "Supply Chain" in dept_names

    hood = store.neighbors(company_id, critical["id"], depth=3)
    hood_names = {n["name"] for n in hood["nodes"]}
    assert KEY_PROJECT in hood_names

    assert impact["impact"]["estimated_revenue_at_risk_cents"] > 1_000_000_00
