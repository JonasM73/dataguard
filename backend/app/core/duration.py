"""Durées ISO 8601, dans le sous-ensemble utile au projet.

Une seule implémentation sert à la fois au contrôle de fraîcheur et à la
validation des entrées de l'API : une durée acceptée par l'API est donc, par
construction, une durée que le moteur sait interpréter.
"""

from __future__ import annotations

import re
from datetime import timedelta

_DURATION = re.compile(
    r"^P(?!$)(?:(?P<days>\d+)D)?(?:T(?!$)(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)


def parse_duration(value: str) -> timedelta:
    """Convertit une durée ISO 8601 restreinte (P1D, P1DT6H, PT15M) en timedelta."""
    match = _DURATION.match(value or "")
    if not match:
        raise ValueError(
            f"Durée ISO 8601 non reconnue : {value!r}. Formats acceptés : P1D, PT6H, PT15M."
        )
    parts = {key: int(raw) for key, raw in match.groupdict(default="0").items()}
    duration = timedelta(
        days=parts["days"],
        hours=parts["hours"],
        minutes=parts["minutes"],
        seconds=parts["seconds"],
    )
    if duration <= timedelta(0):
        raise ValueError(f"La durée doit être strictement positive : {value!r}")
    return duration
