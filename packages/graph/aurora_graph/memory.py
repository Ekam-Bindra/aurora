"""In-memory graph store — default for local SQLite dev and tests."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aurora_graph.types import GraphEdge, GraphNode, GraphSnapshot


class InMemoryGraphStore:
    """Tenant-scoped adjacency-list graph rebuilt from Postgres/SQLite truth."""

    def __init__(self) -> None:
        self._snapshots: Dict[str, GraphSnapshot] = {}

    def replace(self, snapshot: GraphSnapshot) -> None:
        self._snapshots[snapshot.tenant_id] = snapshot

    def get_snapshot(self, tenant_id: str) -> Optional[GraphSnapshot]:
        return self._snapshots.get(tenant_id)

    def _adjacency(
        self, tenant_id: str
    ) -> Tuple[Dict[str, GraphNode], Dict[str, List[GraphEdge]], Dict[str, List[GraphEdge]]]:
        snap = self._snapshots.get(tenant_id)
        if not snap:
            return {}, {}, {}
        nodes = snap.node_map()
        out: Dict[str, List[GraphEdge]] = defaultdict(list)
        rev: Dict[str, List[GraphEdge]] = defaultdict(list)
        for e in snap.edges:
            out[e.source_id].append(e)
            rev[e.target_id].append(e)
        return nodes, out, rev

    def list_nodes(
        self,
        tenant_id: str,
        label: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        snap = self._snapshots.get(tenant_id)
        if not snap:
            return []
        nodes = snap.nodes
        if label:
            nodes = [n for n in nodes if n.label == label]
        return [n.to_dict() for n in nodes[:limit]]

    def neighbors(
        self,
        tenant_id: str,
        node_id: str,
        depth: int = 1,
    ) -> Dict[str, Any]:
        nodes, out, rev = self._adjacency(tenant_id)
        if node_id not in nodes:
            return {"node": None, "nodes": [], "edges": []}

        seen_nodes: Set[str] = {node_id}
        seen_edges: Set[Tuple[str, str, str]] = set()
        frontier = {node_id}
        collected_edges: List[GraphEdge] = []

        for _ in range(max(1, depth)):
            next_frontier: Set[str] = set()
            for nid in frontier:
                for e in out.get(nid, []) + rev.get(nid, []):
                    key = (e.source_id, e.target_id, e.type)
                    if key not in seen_edges:
                        seen_edges.add(key)
                        collected_edges.append(e)
                    other = e.target_id if e.source_id == nid else e.source_id
                    if other not in seen_nodes:
                        seen_nodes.add(other)
                        next_frontier.add(other)
            frontier = next_frontier

        return {
            "node": nodes[node_id].to_dict(),
            "nodes": [nodes[n].to_dict() for n in seen_nodes if n in nodes],
            "edges": [e.to_dict() for e in collected_edges],
        }

    def impact(
        self,
        tenant_id: str,
        node_id: str,
        depth: int = 2,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        nodes, out, _ = self._adjacency(tenant_id)
        if node_id not in nodes:
            return {"node": None, "impact": {}}

        root = nodes[node_id]
        affected_products: List[Dict[str, Any]] = []
        affected_customers: List[Dict[str, Any]] = []
        affected_departments: List[Dict[str, Any]] = []
        affected_employees: List[Dict[str, Any]] = []

        # Vendor failure: SUPPLIES -> Product <- PURCHASED <- Customer
        product_ids: Set[str] = set()
        if root.label == "Vendor":
            for e in out.get(node_id, []):
                if e.type == "SUPPLIES" and e.target_id in nodes:
                    product_ids.add(e.target_id)
                    affected_products.append(nodes[e.target_id].to_dict())

            customer_amounts: Dict[str, int] = defaultdict(int)
            snap = self._snapshots[tenant_id]
            for e in snap.edges:
                if e.type == "PURCHASED" and e.target_id in product_ids:
                    cust_id = e.source_id
                    if cust_id in nodes:
                        customer_amounts[cust_id] += int(e.properties.get("amount_cents", 0))

            total = sum(customer_amounts.values()) or 1
            for cid, amt in sorted(customer_amounts.items(), key=lambda x: -x[1]):
                affected_customers.append(
                    {
                        **nodes[cid].to_dict(),
                        "revenue_share": amt / total,
                        "amount_cents": amt,
                    }
                )

            for e in snap.edges:
                if e.type == "DEPENDS_ON" and e.target_id == node_id:
                    dept_id = e.source_id
                    if dept_id in nodes:
                        affected_departments.append(nodes[dept_id].to_dict())

        elif root.label == "Customer":
            affected_customers.append(root.to_dict())

        # Projects / key people via WORKS_ON / DELIVERS_FOR within depth
        hood = self.neighbors(tenant_id, node_id, depth=depth)
        seen_emp = {e["id"] for e in affected_employees}
        for n in hood["nodes"]:
            if n.get("label") == "Employee" and n["id"] not in seen_emp:
                affected_employees.append(n)

        revenue_at_risk = 0
        if session is not None and affected_customers:
            from aurora_db.models import RevenueRecord

            cust_ids = [c["id"] for c in affected_customers]
            since = date.today().replace(day=1)
            since = since.replace(year=since.year - 1)
            rows = session.execute(
                select(func.sum(RevenueRecord.amount_cents))
                .where(
                    RevenueRecord.company_id == tenant_id,
                    RevenueRecord.customer_id.in_(cust_ids),
                    RevenueRecord.period_month >= since,
                )
            ).scalar()
            revenue_at_risk = int(rows or 0)

        return {
            "node": root.to_dict(),
            "impact": {
                "affected_products": affected_products,
                "affected_customers": affected_customers,
                "affected_departments": affected_departments,
                "affected_employees": affected_employees,
                "estimated_revenue_at_risk_cents": revenue_at_risk,
            },
        }

    def concentration(self, tenant_id: str) -> Dict[str, Any]:
        snap = self._snapshots.get(tenant_id)
        if not snap:
            return {"customers": [], "vendors": []}

        cust_totals: Dict[str, int] = defaultdict(int)
        vend_totals: Dict[str, int] = defaultdict(int)
        nodes = snap.node_map()

        for e in snap.edges:
            if e.type == "GENERATES_REVENUE":
                cust_totals[e.source_id] += int(e.properties.get("amount_cents", 0))
            if e.type == "INCURS_COST":
                vend_totals[e.source_id] += int(e.properties.get("amount_cents", 0))

        def _top_list(totals: Dict[str, int]) -> List[Dict[str, Any]]:
            total = sum(totals.values()) or 1
            items = sorted(totals.items(), key=lambda x: -x[1])[:10]
            return [
                {
                    "name": nodes[cid].name if cid in nodes else cid,
                    "amount_cents": amt,
                    "share": amt / total,
                }
                for cid, amt in items
            ]

        cust_total = sum(cust_totals.values()) or 1
        vend_total = sum(vend_totals.values()) or 1
        cust_top5 = sum(v for _, v in sorted(cust_totals.items(), key=lambda x: -x[1])[:5])
        vend_top5 = sum(v for _, v in sorted(vend_totals.items(), key=lambda x: -x[1])[:5])

        return {
            "customers": {
                "top_5_share": cust_top5 / cust_total,
                "top": _top_list(cust_totals),
            },
            "vendors": {
                "top_5_share": vend_top5 / vend_total,
                "top": _top_list(vend_totals),
            },
        }
