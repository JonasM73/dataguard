"""Orchestration d'une exécution complète.

Ingestion → profilage → contrôles → comparaison → persistance. Chaque étape
ouvre un span et journalise sous le même `run_id`, de sorte qu'un incident se
reconstitue en filtrant sur un seul identifiant.

Un échec technique (source injoignable, fichier vide, encodage illisible) donne
un run enregistré en `failed` avec un message exploitable et un score nul —
jamais une exception qui remonterait telle quelle à l'appelant.
"""

from __future__ import annotations

import copy
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.comparison.diff import RunSnapshot, compare
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.telemetry import span
from app.db.models import Dataset, IngestionRun, QualityResult, RunComparison, SchemaField
from app.ingestion.loader import FetchedFile, IngestionError, fetch_local, fetch_url, read_table
from app.profiling.schema import observe_schema
from app.quality.base import CheckContext, Status
from app.quality.engine import run_checks

logger = get_logger(__name__)


def _previous_run(
    session: Session, dataset_id: uuid.UUID, exclude: uuid.UUID
) -> IngestionRun | None:
    """Dernière exécution exploitable du dataset, pour la comparaison.

    Les runs en échec technique sont écartés : comparer à un run qui n'a rien
    lu produirait une chute de volume de 100 % dénuée de sens.
    """
    statement = (
        select(IngestionRun)
        .where(
            IngestionRun.dataset_id == dataset_id,
            IngestionRun.id != exclude,
            IngestionRun.status.in_([Status.SUCCESS.value, Status.WARNING.value]),
        )
        .order_by(IngestionRun.started_at.desc())
        .limit(1)
    )
    return session.execute(statement).scalar_one_or_none()


def _effective_config(dataset: Dataset) -> dict:
    """Configuration du dataset, la fréquence attendue venant de la colonne.

    La fréquence n'existe qu'à un seul endroit — la colonne `expected_frequency` —
    et elle est injectée ici. Sans cela elle vivrait en double et finirait par
    diverger.
    """
    config = copy.deepcopy(dataset.config or {})
    freshness = config.setdefault("freshness", {})
    freshness["expected_frequency"] = dataset.expected_frequency
    return config


def run_pipeline(
    session: Session,
    dataset: Dataset,
    *,
    local_file: Path | None = None,
    now: datetime | None = None,
) -> IngestionRun:
    """Exécute le pipeline et rend le run persisté."""
    now = now or datetime.now(UTC)
    run = IngestionRun(
        id=uuid.uuid4(), dataset_id=dataset.id, started_at=now, status=Status.FAILED.value
    )
    session.add(run)
    session.flush()

    # Span racine du run. Les étapes ouvertes ensuite en deviennent les enfants
    # et partagent son identifiant de trace ; sans lui, chacune ouvrirait une
    # trace isolée et l'on perdrait justement ce qu'on cherche à observer :
    # l'enchaînement des étapes d'une même exécution.
    with span("pipeline", run_id=str(run.id), dataset=dataset.name):
        return _execute(session, dataset, run, now, local_file)


def _execute(
    session: Session,
    dataset: Dataset,
    run: IngestionRun,
    now: datetime,
    local_file: Path | None,
) -> IngestionRun:
    """Corps du pipeline, exécuté à l'intérieur du span racine."""
    settings = get_settings()
    log = logger.bind(run_id=str(run.id), dataset=dataset.name)
    config = _effective_config(dataset)
    destination = Path(settings.raw_dir) / str(dataset.id) / f"{run.id}.csv"

    try:
        with span("ingestion", run_id=str(run.id), dataset=dataset.name):
            if local_file is not None:
                fetched: FetchedFile = fetch_local(
                    local_file, destination, settings.max_download_bytes
                )
            elif dataset.source.url:
                fetched = fetch_url(dataset.source.url, destination, settings.max_download_bytes)
            else:
                raise IngestionError(
                    "no_source",
                    "Le dataset n'a ni URL de source ni fichier fourni.",
                )
            run.file_size_bytes = fetched.size_bytes
            run.checksum = fetched.checksum
            run.raw_path = str(fetched.path)
            log.info("ingestion.done", size=fetched.size_bytes, origin=fetched.origin)

        with span("profiling", run_id=str(run.id)):
            frame = read_table(fetched.path, config)
            observed = observe_schema(frame, config)
            run.rows_read = len(frame)
            run.columns_read = len(frame.columns)
            log.info("profiling.done", rows=run.rows_read, columns=run.columns_read)

    except IngestionError as exc:
        run.finished_at = datetime.now(UTC)
        run.status = Status.FAILED.value
        run.score = None
        run.error_message = f"[{exc.code}] {exc.message}"
        log.warning("ingestion.failed", code=exc.code, message=exc.message)
        session.flush()
        return run

    previous = _previous_run(session, dataset.id, exclude=run.id)

    # Schéma de référence : celui déclaré sur le dataset, sinon celui du premier
    # run réussi. Tant qu'aucun n'existe, le contrôle de schéma est non
    # applicable plutôt que faussement rassurant.
    reference = dataset.reference_schema
    if not reference and previous and previous.schema_fields:
        reference = {
            "fields": [
                {
                    "column_name": f.column_name,
                    "data_type": f.data_type,
                    "nullable": f.nullable,
                    "position": f.position,
                }
                for f in previous.schema_fields
            ]
        }

    fallback = None
    if fetched.last_modified:
        fallback = (
            fetched.last_modified,
            "http_header" if fetched.origin == "url" else "file_mtime",
        )

    with span("quality", run_id=str(run.id)):
        context = CheckContext(
            df=frame,
            config=config,
            now=now,
            reference_schema=reference,
            previous_rows=previous.rows_read if previous else None,
            observed_schema=observed,
            fallback_freshness=fallback,
        )
        report = run_checks(context)
        run.score = report.score
        run.status = report.status.value
        log.info("quality.done", score=report.score, status=run.status)

    freshness = report.by_name("freshness")
    if freshness and freshness.details.get("freshness_date"):
        run.freshness_date = pd.Timestamp(freshness.details["freshness_date"]).to_pydatetime()
        run.freshness_origin = freshness.details.get("origin")
    else:
        run.freshness_origin = "none"

    session.add_all(
        [
            QualityResult(
                run_id=run.id,
                check_name=r.check_name,
                dimension=r.dimension,
                status=r.status.value,
                weight=r.weight,
                score=r.score,
                failed_count=r.failed_count,
                threshold=r.threshold,
                details=r.details,
            )
            for r in report.results
        ]
    )
    session.add_all(
        [
            SchemaField(
                run_id=run.id,
                column_name=f["column_name"],
                data_type=f["data_type"],
                nullable=f["nullable"],
                position=f["position"],
            )
            for f in observed
        ]
    )

    if previous:
        with span("comparison", run_id=str(run.id), previous_run_id=str(previous.id)):
            diff = compare(
                RunSnapshot(
                    rows=run.rows_read,
                    score=run.score,
                    schema=observed,
                    checks={r.check_name: r.status.value for r in report.results},
                ),
                RunSnapshot(
                    rows=previous.rows_read,
                    score=float(previous.score) if previous.score is not None else None,
                    schema=[
                        {
                            "column_name": f.column_name,
                            "data_type": f.data_type,
                            "nullable": f.nullable,
                            "position": f.position,
                        }
                        for f in previous.schema_fields
                    ],
                    checks={r.check_name: r.status for r in previous.results},
                ),
            )
            session.add(RunComparison(run_id=run.id, previous_run_id=previous.id, **diff))
            log.info("comparison.done", rows_delta=diff["rows_delta"])

    # Le premier run réussi fixe le schéma de référence du dataset.
    if not dataset.reference_schema and report.status is not Status.FAILED:
        dataset.reference_schema = {"fields": observed}

    run.finished_at = datetime.now(UTC)
    session.flush()
    log.info("pipeline.done", status=run.status, duration_ms=run.duration_ms)
    return run
