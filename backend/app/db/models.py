"""Modèles SQLAlchemy.

Les statuts sont stockés en texte plutôt qu'en type énuméré PostgreSQL :
l'ajout d'une valeur ne demande alors aucune migration délicate, et la
validation reste assurée côté Python par `Status`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)  # nul pour un fichier local
    format: Mapped[str] = mapped_column(String(16), nullable=False, default="csv")
    license: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    datasets: Mapped[list[Dataset]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = _pk()
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Durée ISO 8601 (P1D, PT6H). Seule source de vérité : le pipeline l'injecte
    # dans la configuration avant d'exécuter le contrôle de fraîcheur.
    expected_frequency: Mapped[str] = mapped_column(String(32), nullable=False, default="P1D")
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    reference_schema: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    source: Mapped[Source] = relationship(back_populates="datasets")
    runs: Mapped[list[IngestionRun]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[uuid.UUID] = _pk()
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), nullable=False)

    rows_read: Mapped[int | None] = mapped_column(Integer)
    columns_read: Mapped[int | None] = mapped_column(Integer)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    checksum: Mapped[str | None] = mapped_column(String(80))
    raw_path: Mapped[str | None] = mapped_column(Text)

    freshness_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    freshness_origin: Mapped[str | None] = mapped_column(String(16))

    score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    error_message: Mapped[str | None] = mapped_column(Text)

    dataset: Mapped[Dataset] = relationship(back_populates="runs")
    results: Mapped[list[QualityResult]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    schema_fields: Mapped[list[SchemaField]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="SchemaField.position",
    )
    comparison: Mapped[RunComparison | None] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        foreign_keys="RunComparison.run_id",
        uselist=False,
    )

    __table_args__ = (Index("ix_runs_dataset_started", "dataset_id", "started_at"),)

    @property
    def duration_ms(self) -> int | None:
        if not self.finished_at:
            return None
        return int((self.finished_at - self.started_at).total_seconds() * 1000)


class QualityResult(Base):
    __tablename__ = "quality_results"

    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="CASCADE"), nullable=False
    )
    check_name: Mapped[str] = mapped_column(String(64), nullable=False)
    dimension: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    # Le poids est recopié ici : un run reste explicable même si la
    # configuration du dataset change plus tard.
    weight: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    threshold: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    run: Mapped[IngestionRun] = relationship(back_populates="results")

    __table_args__ = (Index("ix_results_run", "run_id"),)


class SchemaField(Base):
    __tablename__ = "schema_fields"

    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="CASCADE"), nullable=False
    )
    column_name: Mapped[str] = mapped_column(String(200), nullable=False)
    data_type: Mapped[str] = mapped_column(String(32), nullable=False)
    nullable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    run: Mapped[IngestionRun] = relationship(back_populates="schema_fields")

    __table_args__ = (Index("ix_schema_run", "run_id"),)


class RunComparison(Base):
    __tablename__ = "run_comparisons"

    id: Mapped[uuid.UUID] = _pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    previous_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="CASCADE"), nullable=False
    )
    rows_delta: Mapped[int | None] = mapped_column(Integer)
    rows_delta_pct: Mapped[float | None] = mapped_column(Numeric(8, 2))
    score_delta: Mapped[float | None] = mapped_column(Numeric(6, 2))
    schema_diff: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    checks_diff: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)

    run: Mapped[IngestionRun] = relationship(back_populates="comparison", foreign_keys=[run_id])
