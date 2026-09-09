"""Socle du moteur de contrôles.

Un contrôle reçoit un contexte (le DataFrame, la configuration du dataset, le
schéma de référence, le run précédent) et rend un `CheckResult`. Il ne connaît
ni la base de données, ni l'API : c'est ce qui permet de le tester sans rien
démarrer, et d'en ajouter un sans toucher au reste de la chaîne.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

import pandas as pd

# Nombre maximal d'exemples d'anomalies conservés par contrôle. Au-delà, le
# détail cesse d'aider à diagnostiquer et alourdit la base pour rien.
MAX_SAMPLES = 20


class Status(StrEnum):
    SUCCESS = "success"
    WARNING = "warning"
    FAILED = "failed"
    SKIPPED = "skipped"  # contrôle non applicable : exclu du score

    @property
    def contribution(self) -> float:
        """Contribution au score pondéré."""
        return {"success": 1.0, "warning": 0.5, "failed": 0.0}.get(self.value, 0.0)

    @property
    def rank(self) -> int:
        """Gravité, pour agréger plusieurs statuts en un seul."""
        return {"skipped": 0, "success": 1, "warning": 2, "failed": 3}[self.value]


def worst(statuses: list[Status]) -> Status:
    """Statut le plus grave d'une liste, `SKIPPED` si la liste est vide."""
    real = [s for s in statuses if s is not Status.SKIPPED]
    if not real:
        return Status.SKIPPED
    return max(real, key=lambda s: s.rank)


@dataclass
class CheckResult:
    check_name: str
    dimension: str
    status: Status
    weight: int
    failed_count: int = 0
    threshold: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def score(self) -> float:
        return self.status.contribution

    def as_dict(self) -> dict[str, Any]:
        return {
            "check_name": self.check_name,
            "dimension": self.dimension,
            "status": self.status.value,
            "weight": self.weight,
            "score": self.score,
            "failed_count": self.failed_count,
            "threshold": self.threshold,
            "details": self.details,
        }


@dataclass
class CheckContext:
    """Tout ce dont un contrôle a besoin, et rien de plus."""

    df: pd.DataFrame
    config: dict[str, Any]
    now: datetime
    reference_schema: dict[str, Any] | None = None
    previous_rows: int | None = None
    observed_schema: list[dict[str, Any]] = field(default_factory=list)
    # Date de repli pour la fraîcheur quand aucune colonne de date n'est
    # exploitable : (date, origine) où origine vaut "http_header" ou
    # "file_mtime". Toujours moins fiable qu'une date portée par la donnée
    # elle-même, d'où l'ordre de priorité.
    fallback_freshness: tuple[datetime, str] | None = None

    @property
    def columns_config(self) -> dict[str, dict[str, Any]]:
        return self.config.get("columns", {})

    @property
    def defaults(self) -> dict[str, float]:
        return self.config.get("defaults", {})

    def weight_of(self, check_name: str) -> int:
        return int(self.config.get("weights", {}).get(check_name, 1))

    def present(self, column: str) -> bool:
        return column in self.df.columns


class Check(Protocol):
    name: str
    dimension: str

    def run(self, ctx: CheckContext) -> CheckResult: ...


def pct(numerator: int, denominator: int) -> float:
    """Pourcentage arrondi, robuste au dénominateur nul."""
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator * 100, 4)


def status_from_pct(value: float, warn: float, fail: float) -> Status:
    """Statut d'une mesure exprimée en pourcentage, selon deux seuils.

    Le seuil d'alerte est franchi dès qu'on le dépasse strictement : mettre
    `warn` à 0 signifie donc « la moindre occurrence déclenche une alerte ».
    """
    if value > fail:
        return Status.FAILED
    if value > warn:
        return Status.WARNING
    return Status.SUCCESS


def coverage(ctx: CheckContext, applies: Any) -> tuple[list[str], list[str]]:
    """Colonnes que la configuration confie à ce contrôle, et celles qui manquent.

    Un contrôle qui ne trouve pas les colonnes qu'on lui a désignées n'a pas
    « rien à signaler » : il n'a rien pu regarder. Sans cette distinction, un
    fichier dont toutes les colonnes ont été renommées ressortirait conforme,
    ce qui est exactement le genre de faux acquittement que DataGuard existe
    pour empêcher.
    """
    configured = [column for column, rules in ctx.columns_config.items() if applies(rules)]
    missing = [column for column in configured if not ctx.present(column)]
    return configured, missing


def coverage_details(configured: list[str], missing: list[str]) -> dict[str, Any]:
    """Fragment de `details` décrivant l'étendue réellement contrôlée."""
    return {
        "configured_columns": len(configured),
        "checked_columns": len(configured) - len(missing),
        "missing_columns": sample(missing),
    }


def sample(values: list[Any], limit: int = MAX_SAMPLES) -> list[Any]:
    return [None if pd.isna(v) else v for v in values[:limit]]
