"""Fixtures partagées.

Les tests ne lisent jamais les fichiers de `data/sample` versionnés : ils les
régénèrent dans un répertoire temporaire avec un instant de référence figé.
Sans cela, la fraîcheur et la cohérence — qui se mesurent par rapport à
« maintenant » — rendraient un verdict différent selon le jour d'exécution, et
la suite se mettrait à échouer toute seule au bout de quelques jours.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

# Instant de référence des tests : figé, donc reproductible.
NOW = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="session")
def now() -> datetime:
    return NOW


@pytest.fixture(scope="session")
def samples(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    from generate_samples import generate_all

    return generate_all(tmp_path_factory.mktemp("samples"), NOW)


@pytest.fixture(scope="session")
def config() -> dict[str, Any]:
    path = REPO_ROOT / "data" / "sample" / "dataset_config.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def reference_schema() -> dict[str, Any]:
    path = REPO_ROOT / "data" / "sample" / "reference_schema.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        "fields": [
            {k: field[k] for k in ("column_name", "data_type", "nullable", "position")}
            for field in raw["fields"]
        ]
    }


@pytest.fixture
def read_sample(samples: dict[str, Path], config: dict[str, Any]):
    """Charge un échantillon exactement comme le fait le pipeline."""
    from app.ingestion.loader import read_table

    def _read(name: str) -> pd.DataFrame:
        return read_table(samples[name], config)

    return _read
