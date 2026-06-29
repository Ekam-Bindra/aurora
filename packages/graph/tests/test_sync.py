"""Graph sync and impact tests."""

from aurora_db.base import Base
from aurora_db.seed.nimbus import CRITICAL_VENDOR, seed_nimbus
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aurora_graph.memory import InMemoryGraphStore
from aurora_graph.sync import sync_company_graph


def test_sync_and_vendor_impact():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    result = seed_nimbus(session, seed=42, scale=0.05, password="test")
    session.commit()
    company_id = result["company_id"]

    snapshot = sync_company_graph(session, company_id)
    store = InMemoryGraphStore()
    store.replace(snapshot)

    vendors = store.list_nodes(company_id, label="Vendor")
    critical = next(v for v in vendors if v["name"] == CRITICAL_VENDOR)
    impact = store.impact(company_id, critical["id"], depth=2, session=session)

    assert impact["node"]["name"] == CRITICAL_VENDOR
    products = impact["impact"]["affected_products"]
    assert len(products) > 0
    customers = impact["impact"]["affected_customers"]
    assert len(customers) > 0
    assert impact["impact"]["estimated_revenue_at_risk_cents"] > 0
