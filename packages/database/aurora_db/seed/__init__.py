"""Demo seeding: personas, the Nimbus generator, and the §7.3 verification self-check."""

from .nimbus import DEMO_SLUG, CheckResult, all_passed, seed_nimbus, verify
from .personas import PERSONAS, ROLE_DEFINITIONS, hash_password

__all__ = [
    "seed_nimbus",
    "verify",
    "all_passed",
    "CheckResult",
    "DEMO_SLUG",
    "PERSONAS",
    "ROLE_DEFINITIONS",
    "hash_password",
]
