"""Endpoints des datasets."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db
from app.api.errors import not_found
from app.api.schemas import (
    DatasetCreate,
    DatasetOut,
    DatasetPatch,
    DatasetSummary,
    LastRunSummary,
    SourceOut,
)
from app.db.models import Dataset, IngestionRun, Source

router = APIRouter(tags=["datasets"])


def _last_run(session: Session, dataset_id: uuid.UUID) -> LastRunSummary | None:
    """Dernière exécution d'un dataset.

    Une requête par dataset : avec quelques datasets suivis, l'optimiser
    prématurément coûterait en lisibilité plus que ça ne rapporterait.
    """
    run = session.execute(
        select(IngestionRun)
        .where(IngestionRun.dataset_id == dataset_id)
        .order_by(IngestionRun.started_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if run is None:
        return None
    return LastRunSummary(
        id=run.id,
        started_at=run.started_at,
        status=run.status,
        score=float(run.score) if run.score is not None else None,
    )


def _summary(session: Session, dataset: Dataset) -> DatasetSummary:
    return DatasetSummary(
        id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        expected_frequency=dataset.expected_frequency,
        active=dataset.active,
        source=SourceOut.model_validate(dataset.source),
        last_run=_last_run(session, dataset.id),
    )


def _get(session: Session, dataset_id: uuid.UUID) -> Dataset:
    dataset = session.execute(
        select(Dataset).options(selectinload(Dataset.source)).where(Dataset.id == dataset_id)
    ).scalar_one_or_none()
    if dataset is None:
        raise not_found("dataset", dataset_id)
    return dataset


@router.get("/datasets", response_model=list[DatasetSummary])
def list_datasets(session: Session = Depends(get_db)) -> list[DatasetSummary]:
    datasets = (
        session.execute(
            select(Dataset).options(selectinload(Dataset.source)).order_by(Dataset.created_at)
        )
        .scalars()
        .all()
    )
    return [_summary(session, d) for d in datasets]


@router.post("/datasets", response_model=DatasetOut, status_code=status.HTTP_201_CREATED)
def create_dataset(payload: DatasetCreate, session: Session = Depends(get_db)) -> DatasetOut:
    if session.get(Source, payload.source_id) is None:
        raise not_found("source", payload.source_id)
    dataset = Dataset(**payload.model_dump())
    session.add(dataset)
    session.flush()
    session.refresh(dataset)
    return _detail(session, dataset)


@router.get("/datasets/{dataset_id}", response_model=DatasetOut)
def get_dataset(dataset_id: uuid.UUID, session: Session = Depends(get_db)) -> DatasetOut:
    return _detail(session, _get(session, dataset_id))


@router.patch("/datasets/{dataset_id}", response_model=DatasetOut)
def patch_dataset(
    dataset_id: uuid.UUID, payload: DatasetPatch, session: Session = Depends(get_db)
) -> DatasetOut:
    dataset = _get(session, dataset_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(dataset, field, value)
    session.flush()
    return _detail(session, dataset)


def _detail(session: Session, dataset: Dataset) -> DatasetOut:
    summary = _summary(session, dataset)
    return DatasetOut(
        **summary.model_dump(),
        config=dataset.config,
        reference_schema=dataset.reference_schema,
        created_at=dataset.created_at,
    )
