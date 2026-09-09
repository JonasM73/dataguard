"""Comparaison de deux exécutions du même dataset.

Le score seul ne dit pas grand-chose : savoir qu'il est passé de 100 à 82 sans
savoir ce qui a bougé n'aide personne. La comparaison répond à la seconde
question du projet — « qu'est-ce qui a changé depuis la dernière fois ? »
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.profiling.schema import diff_schemas


@dataclass
class RunSnapshot:
    """Vue minimale d'une exécution, suffisante pour la comparer à une autre."""

    rows: int | None = None
    score: float | None = None
    schema: list[dict[str, Any]] = field(default_factory=list)
    checks: dict[str, str] = field(default_factory=dict)  # nom du contrôle -> statut


def compare(current: RunSnapshot, previous: RunSnapshot) -> dict[str, Any]:
    """Différences entre l'exécution courante et la précédente."""
    rows_delta: int | None = None
    rows_delta_pct: float | None = None
    if current.rows is not None and previous.rows:
        rows_delta = current.rows - previous.rows
        rows_delta_pct = round(rows_delta / previous.rows * 100, 2)

    score_delta: float | None = None
    if current.score is not None and previous.score is not None:
        score_delta = round(current.score - previous.score, 2)

    checks_diff = [
        {"check_name": name, "from": previous.checks[name], "to": status}
        for name, status in current.checks.items()
        if name in previous.checks and previous.checks[name] != status
    ]
    # Un contrôle qui apparaît ou disparaît est un changement, pas un non-événement.
    checks_diff += [
        {"check_name": name, "from": None, "to": status}
        for name, status in current.checks.items()
        if name not in previous.checks
    ]
    checks_diff += [
        {"check_name": name, "from": status, "to": None}
        for name, status in previous.checks.items()
        if name not in current.checks
    ]

    return {
        "rows_delta": rows_delta,
        "rows_delta_pct": rows_delta_pct,
        "score_delta": score_delta,
        "schema_diff": diff_schemas(previous.schema, current.schema),
        "checks_diff": sorted(checks_diff, key=lambda d: d["check_name"]),
    }
