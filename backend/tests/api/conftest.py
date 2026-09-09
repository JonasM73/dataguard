"""Fixtures des tests d'API.

Ils tournent contre une vraie base PostgreSQL, et non contre SQLite : le projet
s'appuie sur JSONB et sur des index propres à PostgreSQL, si bien qu'une suite
verte sur SQLite ne prouverait rien de ce qui tourne réellement.

La base de test est distincte de la base de développement et ses tables sont
vidées entre chaque test, pour qu'un test ne dépende jamais de ce qu'un autre a
laissé derrière lui.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from datetime import UTC
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db
from app.db.models import Base, Dataset, Source
from app.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[3]

TABLES = [
    "run_comparisons",
    "quality_results",
    "schema_fields",
    "ingestion_runs",
    "datasets",
    "sources",
]


def _test_database_url() -> str:
    if url := os.getenv("DATAGUARD_TEST_DATABASE_URL"):
        return url
    user = os.getenv("POSTGRES_USER", "dataguard")
    password = os.getenv("POSTGRES_PASSWORD", "dataguard")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("POSTGRES_DB", "dataguard") + "_test"
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"


@pytest.fixture(scope="session")
def samples(tmp_path_factory) -> dict:
    """Échantillons ancrés sur l'horloge réelle.

    Ils remplacent ceux de la conftest racine, qui sont figés à un instant de
    référence. Les tests unitaires passent `now` explicitement au moteur ; les
    tests d'API, eux, traversent le pipeline, qui lit l'heure courante. Des
    fichiers datés d'un autre moment y feraient échouer la fraîcheur et la
    cohérence sans qu'aucun code ne soit en cause.
    """
    from datetime import datetime

    from generate_samples import generate_all

    return generate_all(tmp_path_factory.mktemp("api-samples"), datetime.now(UTC))


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(_test_database_url(), future=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - dépend de l'environnement
        pytest.skip(f"Base de test indisponible : {exc}")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(engine) -> Iterator[Session]:
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    session.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session, tmp_path, monkeypatch) -> Iterator[TestClient]:
    # Les fichiers bruts d'un test vont dans un répertoire jetable.
    monkeypatch.setenv("DATAGUARD_RAW_DIR", str(tmp_path / "raw"))
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def dataset(db_session: Session) -> Dataset:
    """Dataset de démonstration, configuré comme la source réelle."""
    config = json.loads(
        (REPO_ROOT / "data" / "sample" / "dataset_config.json").read_text(encoding="utf-8")
    )
    raw_schema = json.loads(
        (REPO_ROOT / "data" / "sample" / "reference_schema.json").read_text(encoding="utf-8")
    )
    source = Source(
        name="source de test",
        url="https://example.org/prix.csv",
        format="csv",
        license="Licence Ouverte 2.0",
    )
    db_session.add(source)
    db_session.flush()

    dataset = Dataset(
        source_id=source.id,
        name="Prix des carburants (test)",
        expected_frequency="P1D",
        config=config,
        reference_schema={
            "fields": [
                {k: f[k] for k in ("column_name", "data_type", "nullable", "position")}
                for f in raw_schema["fields"]
            ]
        },
    )
    db_session.add(dataset)
    db_session.commit()
    return dataset
