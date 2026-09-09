"""Score pondéré et statut global."""

from __future__ import annotations

import pytest

from app.quality.base import CheckResult, Status
from app.quality.engine import compute_score, compute_status


def result(name: str, status: Status, weight: int) -> CheckResult:
    return CheckResult(name, name, status, weight)


def test_documented_example():
    """L'exemple de la documentation : sept contrôles, complétude en alerte,
    volume en échec."""
    results = [
        result("schema", Status.SUCCESS, 3),
        result("types", Status.SUCCESS, 3),
        result("uniqueness", Status.SUCCESS, 3),
        result("completeness", Status.WARNING, 2),
        result("ranges", Status.SUCCESS, 2),
        result("freshness", Status.SUCCESS, 2),
        result("volume", Status.FAILED, 1),
    ]
    assert compute_score(results) == 87.5


def test_skipped_checks_leave_the_denominator():
    """Un contrôle non applicable ne doit ni pénaliser ni gonfler le score."""
    with_skip = [result("a", Status.SUCCESS, 3), result("b", Status.SKIPPED, 3)]
    assert compute_score(with_skip) == 100.0


def test_score_is_none_when_nothing_could_run():
    """Afficher 0 laisserait croire à une qualité nulle alors que rien n'a été mesuré."""
    assert compute_score([result("a", Status.SKIPPED, 3)]) is None
    assert compute_score([]) is None


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ([(Status.SUCCESS, 3), (Status.SUCCESS, 1)], Status.SUCCESS),
        # Un contrôle critique en échec disqualifie le run entier.
        ([(Status.FAILED, 3), (Status.SUCCESS, 1)], Status.FAILED),
        # Un contrôle secondaire en échec n'est qu'une alerte.
        ([(Status.SUCCESS, 3), (Status.FAILED, 1)], Status.WARNING),
        ([(Status.WARNING, 2), (Status.SUCCESS, 3)], Status.WARNING),
        ([(Status.SKIPPED, 3)], Status.SKIPPED),
    ],
)
def test_global_status(statuses, expected):
    results = [result(f"c{i}", s, w) for i, (s, w) in enumerate(statuses)]
    assert compute_status(results, critical_weight=3) is expected


def test_contributions():
    assert Status.SUCCESS.contribution == 1.0
    assert Status.WARNING.contribution == 0.5
    assert Status.FAILED.contribution == 0.0
