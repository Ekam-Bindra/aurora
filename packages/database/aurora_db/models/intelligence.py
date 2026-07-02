"""Group E — Intelligence & decision artifacts (docs/data-model/data-model.md §4).

These are written by later phases (forecasting, risk, simulation, agent, reports). The schema
is defined now so the data model is complete and migrations are stable. Each output persists a
``model_version`` + inputs so any number can be explained later (Data Model §7).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from ..mixins import (
    CreatedAtMixin,
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    utcnow,
)
from ..types import GUID, JSONB


class RiskSignal(UUIDPrimaryKeyMixin, TenantScopedMixin, Base):
    __tablename__ = "risk_signal"
    __table_args__ = (
        CheckConstraint(
            "dimension in ('financial','customer_concentration','vendor_supply',"
            "'operational','liquidity','talent','compliance','market')",
            name="dimension_valid",
        ),
        CheckConstraint("score >= 0 and score <= 100", name="score_range"),
        CheckConstraint(
            "severity in ('low','moderate','high','critical')", name="severity_valid"
        ),
    )

    dimension: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(32))
    entity_id: Mapped[Optional[str]] = mapped_column(GUID)
    drivers: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    recommended_actions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    model_version: Mapped[Optional[str]] = mapped_column(String(32))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class Forecast(UUIDPrimaryKeyMixin, TenantScopedMixin, CreatedAtMixin, Base):
    __tablename__ = "forecast"
    __table_args__ = (
        CheckConstraint("granularity in ('month','quarter')", name="granularity_valid"),
    )

    metric: Mapped[str] = mapped_column(String(48), nullable=False)
    granularity: Mapped[str] = mapped_column(String(16), nullable=False, default="month")
    horizon_periods: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    points: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    accuracy: Mapped[Optional[dict]] = mapped_column(JSONB)
    assumptions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    model_version: Mapped[Optional[str]] = mapped_column(String(32))
    created_by: Mapped[Optional[str]] = mapped_column(GUID)


class Scenario(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "scenario"
    __table_args__ = (
        CheckConstraint(
            "status in ('draft','queued','running','completed','failed')",
            name="status_valid",
        ),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    assumptions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    horizon_periods: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=12)
    trials: Mapped[int] = mapped_column(Integer, nullable=False, default=10000)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    created_by: Mapped[Optional[str]] = mapped_column(GUID)


class SimulationResult(UUIDPrimaryKeyMixin, TenantScopedMixin, CreatedAtMixin, Base):
    __tablename__ = "simulation_result"

    scenario_id: Mapped[str] = mapped_column(
        GUID, ForeignKey("scenario.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # One simulation run produces one row per metric; rows share a run_id so the run
    # can be reconstructed across processes (nullable for pre-0002 rows).
    run_id: Mapped[Optional[str]] = mapped_column(GUID, index=True)
    metric: Mapped[str] = mapped_column(String(48), nullable=False)
    summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    distribution: Mapped[Optional[dict]] = mapped_column(JSONB)
    risk_deltas: Mapped[Optional[dict]] = mapped_column(JSONB)
    recommendations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    driver_sensitivity: Mapped[Optional[list]] = mapped_column(JSONB)
    seed: Mapped[Optional[int]] = mapped_column(Integer)
    trials: Mapped[int] = mapped_column(Integer, nullable=False)
    model_version: Mapped[Optional[str]] = mapped_column(String(32))


class Recommendation(UUIDPrimaryKeyMixin, TenantScopedMixin, CreatedAtMixin, Base):
    __tablename__ = "recommendation"
    __table_args__ = (
        CheckConstraint("priority between 1 and 5", name="priority_range"),
        CheckConstraint(
            "status in ('open','accepted','dismissed','done')", name="status_valid"
        ),
    )

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[Optional[str]] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    expected_impact: Mapped[Optional[dict]] = mapped_column(JSONB)
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    entity_type: Mapped[Optional[str]] = mapped_column(String(32))
    entity_id: Mapped[Optional[str]] = mapped_column(GUID)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")


class AIInteraction(UUIDPrimaryKeyMixin, TenantScopedMixin, CreatedAtMixin, Base):
    __tablename__ = "ai_interaction"

    user_id: Mapped[Optional[str]] = mapped_column(GUID)
    session_id: Mapped[Optional[str]] = mapped_column(GUID, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[Optional[str]] = mapped_column(Text)
    tools_used: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    citations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    provider: Mapped[Optional[str]] = mapped_column(String(32))
    model: Mapped[Optional[str]] = mapped_column(String(64))
    tokens_input: Mapped[Optional[int]] = mapped_column(Integer)
    tokens_output: Mapped[Optional[int]] = mapped_column(Integer)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)


class BoardReport(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    __tablename__ = "board_report"
    __table_args__ = (
        CheckConstraint(
            "status in ('draft','in_review','approved','published')", name="status_valid"
        ),
    )

    title: Mapped[str] = mapped_column(Text, nullable=False)
    period_start: Mapped[Optional[date]] = mapped_column(Date)
    period_end: Mapped[Optional[date]] = mapped_column(Date)
    sections: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    content: Mapped[Optional[dict]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    export_url: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[str]] = mapped_column(GUID)
    approved_by: Mapped[Optional[str]] = mapped_column(GUID)


class IngestionJob(UUIDPrimaryKeyMixin, TenantScopedMixin, CreatedAtMixin, Base):
    """Ingestion job status shared across API instances (upload + connector sync)."""

    __tablename__ = "ingestion_job"
    __table_args__ = (
        CheckConstraint(
            "status in ('queued','running','completed','failed')", name="status_valid"
        ),
    )

    target: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[Optional[str]] = mapped_column(
        GUID, ForeignKey("data_source.id", ondelete="SET NULL")
    )
    filename: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    rows_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    lineage_ref: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
