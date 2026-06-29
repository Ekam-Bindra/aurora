"""Seeded roles + persona logins (docs/data-model/demo-dataset-spec.md §8).

The role -> permission matrix mirrors ``apps/api/aurora/core/rbac.py`` (the runtime authority).
We persist it on ``role.permissions`` so the database is self-describing; runtime authorization
still derives from the role name via the API's RBAC module.

The password hasher replicates the API's PBKDF2-SHA256 format exactly so seeded users
authenticate through ``apps/api`` without a re-hash.
"""

import base64
import hashlib
import os

_PBKDF2_ITERATIONS = 200_000
_ALGO_TAG = "pbkdf2_sha256"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def hash_password(password: str, *, iterations: int = _PBKDF2_ITERATIONS) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{_ALGO_TAG}${iterations}${_b64(salt)}${_b64(dk)}"


# Canonical role names (the 8 personas) — must match apps/api Role names.
ROLE_DEFINITIONS = {
    "CEO": {
        "description": "Chief Executive Officer — full read + decision tooling.",
        "permissions": [
            "read:financials", "read:operations", "read:graph", "run:forecast",
            "run:simulation", "use:ai_agent", "create:board_report",
            "approve:board_report", "view:audit_log",
        ],
    },
    "CFO": {
        "description": "Chief Financial Officer — financial authority + data sources.",
        "permissions": [
            "read:financials", "write:financials", "read:operations", "read:graph",
            "run:forecast", "run:simulation", "use:ai_agent", "create:board_report",
            "approve:board_report", "manage:data_sources", "view:audit_log",
        ],
    },
    "COO": {
        "description": "Chief Operating Officer — operations + decision tooling.",
        "permissions": [
            "read:financials", "read:operations", "read:graph", "run:forecast",
            "run:simulation", "use:ai_agent",
        ],
    },
    "Chief Strategy Officer": {
        "description": "Strategy — analysis + board reporting.",
        "permissions": [
            "read:financials", "read:operations", "read:graph", "run:forecast",
            "run:simulation", "use:ai_agent", "create:board_report",
        ],
    },
    "Finance Analyst": {
        "description": "Finance Analyst — builds and maintains financial data.",
        "permissions": [
            "read:financials", "write:financials", "read:operations", "read:graph",
            "run:forecast", "use:ai_agent", "manage:data_sources", "create:board_report",
        ],
    },
    "Operations Manager": {
        "description": "Operations Manager — operational read + assistant.",
        "permissions": ["read:operations", "read:graph", "read:financials", "use:ai_agent"],
    },
    "Department Head": {
        "description": "Department Head — scoped operational read + assistant.",
        "permissions": ["read:operations", "read:graph", "read:financials", "use:ai_agent"],
    },
    "System Administrator": {
        "description": "Administrator — tenant, users, data sources, and audit.",
        "permissions": [
            "manage:data_sources", "manage:users", "view:audit_log", "manage:workspace",
        ],
    },
}

# (full_name, email, title, role_name)
PERSONAS = [
    ("Dana Reyes", "ceo@nimbus.test", "Chief Executive Officer", "CEO"),
    ("Marcus Lin", "cfo@nimbus.test", "Chief Financial Officer", "CFO"),
    ("Priya Anand", "coo@nimbus.test", "Chief Operating Officer", "COO"),
    ("Sofia Marin", "strategy@nimbus.test", "Chief Strategy Officer", "Chief Strategy Officer"),
    ("Tom Becker", "analyst@nimbus.test", "Finance Analyst", "Finance Analyst"),
    ("Wei Zhang", "ops@nimbus.test", "Operations Manager", "Operations Manager"),
    ("Aisha Khan", "depthead@nimbus.test", "Head of Sales", "Department Head"),
    ("Nimbus Admin", "admin@nimbus.test", "System Administrator", "System Administrator"),
]
