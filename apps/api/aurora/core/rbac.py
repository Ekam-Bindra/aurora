"""Role-Based Access Control.

Permissions are ``action:resource`` strings; roles bundle permissions; the 8 product personas
(docs/00-overview-and-vision.md §2) map to the permission matrix in
docs/architecture/system-architecture.md §7.2. ``AuthContext`` is the resolved identity for a
request, built statelessly from JWT claims. ``require_permission`` is a FastAPI dependency
factory that guards routes.

Fine-grained department/project *scoping* (the "scoped"/"partial" cells in the matrix) is
modeled here via ``scope_type``/``scope_id`` and enforced at the data layer in Phase 2 once
departments/projects exist; Phase 1 grants the base permission at tenant scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List


class Permission:
    READ_FINANCIALS = "read:financials"
    WRITE_FINANCIALS = "write:financials"
    READ_OPERATIONS = "read:operations"
    READ_GRAPH = "read:graph"
    RUN_FORECAST = "run:forecast"
    RUN_SIMULATION = "run:simulation"
    USE_AI_AGENT = "use:ai_agent"
    CREATE_BOARD_REPORT = "create:board_report"
    APPROVE_BOARD_REPORT = "approve:board_report"
    MANAGE_DATA_SOURCES = "manage:data_sources"
    MANAGE_USERS = "manage:users"
    VIEW_AUDIT_LOG = "view:audit_log"
    MANAGE_WORKSPACE = "manage:workspace"


# Canonical role names (the 8 personas).
class Role:
    CEO = "CEO"
    CFO = "CFO"
    COO = "COO"
    STRATEGY = "Chief Strategy Officer"
    ANALYST = "Finance Analyst"
    OPS_MANAGER = "Operations Manager"
    DEPT_HEAD = "Department Head"
    ADMIN = "System Administrator"


P = Permission

ROLE_PERMISSIONS: Dict[str, FrozenSet[str]] = {
    Role.CEO: frozenset(
        {
            P.READ_FINANCIALS, P.READ_OPERATIONS, P.READ_GRAPH, P.RUN_FORECAST,
            P.RUN_SIMULATION, P.USE_AI_AGENT, P.CREATE_BOARD_REPORT,
            P.APPROVE_BOARD_REPORT, P.VIEW_AUDIT_LOG,
        }
    ),
    Role.CFO: frozenset(
        {
            P.READ_FINANCIALS, P.WRITE_FINANCIALS, P.READ_OPERATIONS, P.READ_GRAPH,
            P.RUN_FORECAST, P.RUN_SIMULATION, P.USE_AI_AGENT, P.CREATE_BOARD_REPORT,
            P.APPROVE_BOARD_REPORT, P.MANAGE_DATA_SOURCES, P.VIEW_AUDIT_LOG,
        }
    ),
    Role.COO: frozenset(
        {
            P.READ_FINANCIALS, P.READ_OPERATIONS, P.READ_GRAPH, P.RUN_FORECAST,
            P.RUN_SIMULATION, P.USE_AI_AGENT,
        }
    ),
    Role.STRATEGY: frozenset(
        {
            P.READ_FINANCIALS, P.READ_OPERATIONS, P.READ_GRAPH, P.RUN_FORECAST,
            P.RUN_SIMULATION, P.USE_AI_AGENT, P.CREATE_BOARD_REPORT,
        }
    ),
    Role.ANALYST: frozenset(
        {
            P.READ_FINANCIALS, P.WRITE_FINANCIALS, P.READ_OPERATIONS, P.READ_GRAPH,
            P.RUN_FORECAST, P.USE_AI_AGENT, P.MANAGE_DATA_SOURCES, P.CREATE_BOARD_REPORT,
        }
    ),
    Role.OPS_MANAGER: frozenset(
        {P.READ_OPERATIONS, P.READ_GRAPH, P.READ_FINANCIALS, P.USE_AI_AGENT}
    ),
    Role.DEPT_HEAD: frozenset(
        {P.READ_OPERATIONS, P.READ_GRAPH, P.READ_FINANCIALS, P.USE_AI_AGENT}
    ),
    Role.ADMIN: frozenset(
        {P.MANAGE_DATA_SOURCES, P.MANAGE_USERS, P.VIEW_AUDIT_LOG, P.MANAGE_WORKSPACE}
    ),
}


def permissions_for_roles(roles: List[str]) -> FrozenSet[str]:
    granted: set = set()
    for role in roles:
        granted |= ROLE_PERMISSIONS.get(role, frozenset())
    return frozenset(granted)


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    tenant_id: str
    email: str
    roles: List[str] = field(default_factory=list)
    permissions: FrozenSet[str] = field(default_factory=frozenset)
    scope_type: str = "tenant"  # tenant | department | project
    scope_id: str = ""

    def has(self, permission: str) -> bool:
        return permission in self.permissions
