"""All ORM models. Importing this module registers every table on ``Base.metadata``."""

from .commercial import Contract, Customer, Product, Vendor
from .financial import Expense, Invoice, InvoiceLineItem, RevenueRecord
from .identity import AppUser, AuditLog, Company, DataSource, Role, UserRole
from .intelligence import (
    AIInteraction,
    BoardReport,
    Forecast,
    Recommendation,
    RiskSignal,
    Scenario,
    SimulationResult,
)
from .org import Department, Employee, Project, ProjectAssignment

__all__ = [
    # identity & access
    "Company",
    "Role",
    "AppUser",
    "UserRole",
    "DataSource",
    "AuditLog",
    # org & people
    "Department",
    "Employee",
    "Project",
    "ProjectAssignment",
    # commercial
    "Customer",
    "Vendor",
    "Product",
    "Contract",
    # financial
    "Invoice",
    "InvoiceLineItem",
    "Expense",
    "RevenueRecord",
    # intelligence
    "RiskSignal",
    "Forecast",
    "Scenario",
    "SimulationResult",
    "Recommendation",
    "AIInteraction",
    "BoardReport",
]
