"""Schémas Pydantic de l'API.

Ce sont eux qui produisent la documentation Swagger et, par génération, les
types TypeScript du dashboard : un changement de contrat casse le build du
frontend au lieu de casser l'affichage une fois en ligne.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.duration import parse_duration


def _valid_duration(value: str | None) -> str | None:
    """Rejette une fréquence que le moteur ne saurait pas interpréter."""
    if value is not None:
        parse_duration(value)
    return value


T = TypeVar("T")

# Le contrat déclare les statuts explicitement plutôt qu'en texte libre : ils
# apparaissent ainsi dans Swagger, et les types TypeScript engendrés obligent
# le dashboard à traiter exactement ces quatre cas.
CheckStatus = Literal["success", "warning", "failed", "skipped"]


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


# --------------------------------------------------------------------- sources


class SourceCreate(BaseModel):
    name: str = Field(..., max_length=200, examples=["data.economie.gouv.fr"])
    url: str | None = Field(None, examples=["https://example.org/prix.csv"])
    format: str = Field("csv", pattern="^(csv)$")
    license: str | None = Field(None, examples=["Licence Ouverte / Open Licence 2.0"])

    @field_validator("url")
    @classmethod
    def _https_only(cls, value: str | None) -> str | None:
        if value and not value.lower().startswith("https://"):
            raise ValueError("Seules les URL https sont acceptées.")
        return value


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    url: str | None
    format: str
    license: str | None
    created_at: datetime


# -------------------------------------------------------------------- datasets


class DatasetCreate(BaseModel):
    source_id: uuid.UUID
    name: str = Field(..., max_length=200)
    description: str | None = None
    expected_frequency: str = Field("P1D", examples=["P1D", "PT6H"])
    config: dict[str, Any] = Field(default_factory=dict)
    reference_schema: dict[str, Any] | None = None

    _check_frequency = field_validator("expected_frequency")(_valid_duration)


class DatasetPatch(BaseModel):
    name: str | None = Field(None, max_length=200)
    description: str | None = None
    expected_frequency: str | None = Field(None, examples=["P1D", "PT6H"])
    config: dict[str, Any] | None = None
    reference_schema: dict[str, Any] | None = None
    active: bool | None = None

    _check_frequency = field_validator("expected_frequency")(_valid_duration)


class LastRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    started_at: datetime
    status: CheckStatus
    score: float | None


class DatasetSummary(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    expected_frequency: str
    active: bool
    source: SourceOut
    last_run: LastRunSummary | None = None


class DatasetOut(DatasetSummary):
    config: dict[str, Any]
    reference_schema: dict[str, Any] | None
    created_at: datetime


# ------------------------------------------------------------------------ runs


class RunCreate(BaseModel):
    dataset_id: uuid.UUID


class QualityResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    check_name: str
    dimension: str
    status: CheckStatus
    weight: int
    score: float
    failed_count: int
    threshold: dict[str, Any]
    details: dict[str, Any]


class SchemaFieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    column_name: str
    data_type: str
    nullable: bool
    position: int


class RenamedColumn(BaseModel):
    from_: str = Field(..., alias="from")
    to: str


class TypeChangedColumn(BaseModel):
    column: str
    from_: str = Field(..., alias="from")
    to: str


class SchemaDiff(BaseModel):
    """Différences de schéma entre deux exécutions.

    Décrit explicitement plutôt qu'en objet libre : c'est ce qui permet au
    dashboard d'être vérifié par le compilateur au lieu de deviner la forme.
    """

    # Obligatoires et non facultatives : le moteur renvoie toujours les quatre
    # listes, éventuellement vides. Les déclarer optionnelles obligerait le
    # dashboard à gérer une absence qui ne se produit jamais.
    added: list[str]
    removed: list[str]
    renamed: list[RenamedColumn]
    type_changed: list[TypeChangedColumn]


class CheckDiff(BaseModel):
    check_name: str
    from_: CheckStatus | None = Field(..., alias="from")
    to: CheckStatus | None


class RunComparisonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    previous_run_id: uuid.UUID
    rows_delta: int | None
    rows_delta_pct: float | None
    score_delta: float | None
    schema_diff: SchemaDiff
    checks_diff: list[CheckDiff]


class Freshness(BaseModel):
    date: datetime | None
    origin: str | None
    age_hours: float | None


class RunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    status: CheckStatus
    score: float | None
    rows_read: int | None
    columns_read: int | None
    error_message: str | None


class RunDetail(RunSummary):
    file_size_bytes: int | None
    checksum: str | None
    freshness: Freshness
    results: list[QualityResultOut]
    schema_fields: list[SchemaFieldOut] = Field(
        ..., serialization_alias="schema", validation_alias="schema_fields"
    )
    comparison: RunComparisonOut | None
