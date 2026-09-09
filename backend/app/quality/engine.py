"""Exécution des contrôles, calcul du score et du statut global.

Le score est une aide à la lecture, pas un verdict. Il n'est donc jamais publié
sans le détail des contrôles qui le composent, et les poids employés sont
recopiés dans chaque résultat : un run consulté dans six mois reste explicable
même si la configuration a changé entre-temps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.quality.base import CheckContext, CheckResult, Status
from app.quality.checks import ALL_CHECKS

# Poids à partir duquel l'échec d'un seul contrôle disqualifie tout le run.
DEFAULT_CRITICAL_WEIGHT = 3


@dataclass
class QualityReport:
    results: list[CheckResult]
    score: float | None
    status: Status

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "status": self.status.value,
            "results": [r.as_dict() for r in self.results],
        }

    def by_name(self, name: str) -> CheckResult | None:
        return next((r for r in self.results if r.check_name == name), None)


def compute_score(results: list[CheckResult]) -> float | None:
    """Moyenne pondérée des contributions, les contrôles non applicables exclus.

    Rend `None` si aucun contrôle n'a pu s'exécuter : afficher 0 laisserait
    croire à une qualité nulle alors que rien n'a été mesuré.
    """
    scored = [r for r in results if r.status is not Status.SKIPPED]
    total_weight = sum(r.weight for r in scored)
    if total_weight == 0:
        return None
    weighted = sum(r.weight * r.score for r in scored)
    return round(weighted / total_weight * 100, 2)


def compute_status(results: list[CheckResult], critical_weight: int) -> Status:
    """Statut global du run à partir des statuts individuels."""
    scored = [r for r in results if r.status is not Status.SKIPPED]
    if not scored:
        return Status.SKIPPED
    if any(r.status is Status.FAILED and r.weight >= critical_weight for r in scored):
        return Status.FAILED
    if any(r.status in (Status.WARNING, Status.FAILED) for r in scored):
        return Status.WARNING
    return Status.SUCCESS


def run_checks(ctx: CheckContext, checks: list[Any] | None = None) -> QualityReport:
    """Exécute tous les contrôles et agrège leur résultat."""
    results = [check.run(ctx) for check in (checks or ALL_CHECKS)]
    critical = int(ctx.config.get("critical_weight", DEFAULT_CRITICAL_WEIGHT))
    return QualityReport(
        results=results,
        score=compute_score(results),
        status=compute_status(results, critical),
    )
