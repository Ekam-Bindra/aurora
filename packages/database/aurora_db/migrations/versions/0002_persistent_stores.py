"""Persistent stores for board reports, ingestion jobs, and simulation runs.

Revision ID: 0002_persistent_stores
Revises: 0001_initial
Create Date: 2026-07-01

Adds what the Phase 6–8 services need to survive multi-instance deployments
(ECS runs two API tasks): ``board_report.content``, run-grouping columns on
``simulation_result`` (``run_id``, ``seed``, ``driver_sensitivity``), and the
``ingestion_job`` table.

Written defensively: the 0001 baseline creates tables from ``Base.metadata``,
so a fresh database already includes these columns/tables when 0001 runs with
current models. Each step therefore checks the live schema first and no-ops
when the target already exists; only databases created before this revision
get real ALTERs.
"""

import sqlalchemy as sa
from alembic import op

from aurora_db.types import GUID, JSONB

revision = "0002_persistent_stores"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _columns(inspector, table: str) -> set:
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "content" not in _columns(inspector, "board_report"):
        op.add_column("board_report", sa.Column("content", JSONB(), nullable=True))

    sim_cols = _columns(inspector, "simulation_result")
    if "run_id" not in sim_cols:
        op.add_column("simulation_result", sa.Column("run_id", GUID(), nullable=True))
        op.create_index(
            "ix_simulation_result_run_id", "simulation_result", ["run_id"]
        )
    if "seed" not in sim_cols:
        op.add_column("simulation_result", sa.Column("seed", sa.Integer(), nullable=True))
    if "driver_sensitivity" not in sim_cols:
        op.add_column(
            "simulation_result", sa.Column("driver_sensitivity", JSONB(), nullable=True)
        )

    if "ingestion_job" not in inspector.get_table_names():
        op.create_table(
            "ingestion_job",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column(
                "company_id",
                GUID(),
                sa.ForeignKey("company.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("target", sa.String(32), nullable=False),
            sa.Column(
                "source_id",
                GUID(),
                sa.ForeignKey("data_source.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("filename", sa.Text(), nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
            sa.Column("rows_total", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("rows_inserted", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("rows_updated", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("rows_rejected", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("errors", JSONB(), nullable=False, server_default="[]"),
            sa.Column("lineage_ref", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.CheckConstraint(
                "status in ('queued','running','completed','failed')", name="status_valid"
            ),
        )
        op.create_index(
            "ix_ingestion_job_company_id", "ingestion_job", ["company_id"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "ingestion_job" in inspector.get_table_names():
        op.drop_table("ingestion_job")

    sim_cols = _columns(inspector, "simulation_result")
    if "driver_sensitivity" in sim_cols:
        op.drop_column("simulation_result", "driver_sensitivity")
    if "seed" in sim_cols:
        op.drop_column("simulation_result", "seed")
    if "run_id" in sim_cols:
        op.drop_index("ix_simulation_result_run_id", table_name="simulation_result")
        op.drop_column("simulation_result", "run_id")

    if "content" in _columns(inspector, "board_report"):
        op.drop_column("board_report", "content")
