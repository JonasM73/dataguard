"""Schéma initial : sources, datasets, exécutions, résultats, schémas, comparaisons.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-09
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("url", sa.Text()),
        sa.Column("format", sa.String(16), nullable=False, server_default="csv"),
        sa.Column("license", sa.String(200)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "datasets",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "source_id", UUID, sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("expected_frequency", sa.String(32), nullable=False, server_default="P1D"),
        sa.Column("config", JSONB, nullable=False, server_default="{}"),
        sa.Column("reference_schema", JSONB),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "dataset_id", UUID, sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("rows_read", sa.Integer()),
        sa.Column("columns_read", sa.Integer()),
        sa.Column("file_size_bytes", sa.BigInteger()),
        sa.Column("checksum", sa.String(80)),
        sa.Column("raw_path", sa.Text()),
        sa.Column("freshness_date", sa.DateTime(timezone=True)),
        sa.Column("freshness_origin", sa.String(16)),
        sa.Column("score", sa.Numeric(5, 2)),
        sa.Column("error_message", sa.Text()),
    )
    # L'historique d'un dataset se lit toujours du plus récent au plus ancien.
    op.create_index("ix_runs_dataset_started", "ingestion_runs", ["dataset_id", "started_at"])

    op.create_table(
        "quality_results",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "run_id", UUID, sa.ForeignKey("ingestion_runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("check_name", sa.String(64), nullable=False),
        sa.Column("dimension", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("score", sa.Numeric(3, 2), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("threshold", JSONB, nullable=False, server_default="{}"),
        sa.Column("details", JSONB, nullable=False, server_default="{}"),
    )
    op.create_index("ix_results_run", "quality_results", ["run_id"])

    op.create_table(
        "schema_fields",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "run_id", UUID, sa.ForeignKey("ingestion_runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("column_name", sa.String(200), nullable=False),
        sa.Column("data_type", sa.String(32), nullable=False),
        sa.Column("nullable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("position", sa.Integer(), nullable=False),
    )
    op.create_index("ix_schema_run", "schema_fields", ["run_id"])

    op.create_table(
        "run_comparisons",
        sa.Column("id", UUID, primary_key=True),
        # Un run n'est comparé qu'une fois : la contrainte d'unicité l'impose.
        sa.Column(
            "run_id",
            UUID,
            sa.ForeignKey("ingestion_runs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "previous_run_id",
            UUID,
            sa.ForeignKey("ingestion_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rows_delta", sa.Integer()),
        sa.Column("rows_delta_pct", sa.Numeric(8, 2)),
        sa.Column("score_delta", sa.Numeric(6, 2)),
        sa.Column("schema_diff", JSONB, nullable=False, server_default="{}"),
        sa.Column("checks_diff", JSONB, nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_table("run_comparisons")
    op.drop_index("ix_schema_run", table_name="schema_fields")
    op.drop_table("schema_fields")
    op.drop_index("ix_results_run", table_name="quality_results")
    op.drop_table("quality_results")
    op.drop_index("ix_runs_dataset_started", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
    op.drop_table("datasets")
    op.drop_table("sources")
