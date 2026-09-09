"""Endpoints des exécutions."""

from __future__ import annotations

import shutil
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db
from app.api.errors import APIError, not_found
from app.api.schemas import (
    Freshness,
    Page,
    QualityResultOut,
    RunComparisonOut,
    RunCreate,
    RunDetail,
    RunSummary,
    SchemaFieldOut,
)
from app.db.models import Dataset, IngestionRun
from app.pipeline import run_pipeline

router = APIRouter(tags=["runs"])


def _load(session: Session, run_id: uuid.UUID) -> IngestionRun:
    statement = (
        select(IngestionRun)
        .options(
            selectinload(IngestionRun.results),
            selectinload(IngestionRun.schema_fields),
            selectinload(IngestionRun.comparison),
        )
        .where(IngestionRun.id == run_id)
    )
    run = session.execute(statement).scalar_one_or_none()
    if run is None:
        raise not_found("run", run_id)
    return run


def _freshness(run: IngestionRun) -> Freshness:
    age = None
    if run.freshness_date:
        delta = datetime.now(UTC) - run.freshness_date
        age = round(delta.total_seconds() / 3600, 2)
    return Freshness(date=run.freshness_date, origin=run.freshness_origin, age_hours=age)


def to_detail(run: IngestionRun) -> RunDetail:
    return RunDetail(
        id=run.id,
        dataset_id=run.dataset_id,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_ms=run.duration_ms,
        status=run.status,
        score=float(run.score) if run.score is not None else None,
        rows_read=run.rows_read,
        columns_read=run.columns_read,
        error_message=run.error_message,
        file_size_bytes=run.file_size_bytes,
        checksum=run.checksum,
        freshness=_freshness(run),
        results=[QualityResultOut.model_validate(r) for r in run.results],
        schema_fields=[SchemaFieldOut.model_validate(f) for f in run.schema_fields],
        comparison=(RunComparisonOut.model_validate(run.comparison) if run.comparison else None),
    )


def _dataset(session: Session, dataset_id: uuid.UUID) -> Dataset:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise not_found("dataset", dataset_id)
    return dataset


@router.post(
    "/runs",
    response_model=RunDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Lancer une exécution depuis l'URL de la source",
)
def create_run(payload: RunCreate, session: Session = Depends(get_db)) -> RunDetail:
    """Exécute le pipeline de bout en bout.

    Le traitement est synchrone : un dataset de quelques mégaoctets se traite en
    quelques secondes, ce qui ne justifie pas d'introduire une file de tâches.
    """
    dataset = _dataset(session, payload.dataset_id)
    run = run_pipeline(session, dataset)
    session.flush()
    return to_detail(_load(session, run.id))


@router.post(
    "/runs/upload",
    response_model=RunDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Lancer une exécution à partir d'un fichier envoyé",
)
def create_run_from_upload(
    dataset_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
) -> RunDetail:
    dataset = _dataset(session, dataset_id)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temporary:
        shutil.copyfileobj(file.file, temporary)
        staged = Path(temporary.name)
    try:
        run = run_pipeline(session, dataset, local_file=staged)
    finally:
        staged.unlink(missing_ok=True)
    session.flush()
    return to_detail(_load(session, run.id))


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: uuid.UUID, session: Session = Depends(get_db)) -> RunDetail:
    return to_detail(_load(session, run_id))


@router.get("/runs/{run_id}/results", response_model=list[QualityResultOut])
def get_results(run_id: uuid.UUID, session: Session = Depends(get_db)) -> list[QualityResultOut]:
    return [QualityResultOut.model_validate(r) for r in _load(session, run_id).results]


@router.get("/runs/{run_id}/schema", response_model=list[SchemaFieldOut])
def get_schema(run_id: uuid.UUID, session: Session = Depends(get_db)) -> list[SchemaFieldOut]:
    return [SchemaFieldOut.model_validate(f) for f in _load(session, run_id).schema_fields]


@router.get(
    "/runs/{run_id}/comparison",
    response_model=RunComparisonOut,
    responses={204: {"description": "Première exécution : rien à comparer"}},
)
def get_comparison(run_id: uuid.UUID, session: Session = Depends(get_db)) -> Response:
    run = _load(session, run_id)
    if run.comparison is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return JSONResponse(
        content=RunComparisonOut.model_validate(run.comparison).model_dump(
            mode="json", by_alias=True
        ),
        status_code=status.HTTP_200_OK,
    )


@router.get("/runs/{run_id}/report", summary="Rapport JSON complet, téléchargeable")
def get_report(run_id: uuid.UUID, session: Session = Depends(get_db)) -> Response:
    run = _load(session, run_id)
    body = to_detail(run).model_dump(mode="json", by_alias=True)
    return JSONResponse(
        content=body,
        status_code=status.HTTP_200_OK,
        headers={"Content-Disposition": f'attachment; filename="dataguard-run-{run_id}.json"'},
    )


@router.get("/datasets/{dataset_id}/runs", response_model=Page[RunSummary])
def list_runs(
    dataset_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
    session: Session = Depends(get_db),
) -> Page[RunSummary]:
    _dataset(session, dataset_id)
    if not 1 <= limit <= 100:
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "invalid_pagination",
            "limit doit être compris entre 1 et 100.",
        )

    total = session.execute(
        select(func.count(IngestionRun.id)).where(IngestionRun.dataset_id == dataset_id)
    ).scalar_one()
    rows = (
        session.execute(
            select(IngestionRun)
            .where(IngestionRun.dataset_id == dataset_id)
            .order_by(IngestionRun.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )

    return Page[RunSummary](
        items=[
            RunSummary(
                id=r.id,
                dataset_id=r.dataset_id,
                started_at=r.started_at,
                finished_at=r.finished_at,
                duration_ms=r.duration_ms,
                status=r.status,
                score=float(r.score) if r.score is not None else None,
                rows_read=r.rows_read,
                columns_read=r.columns_read,
                error_message=r.error_message,
            )
            for r in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
