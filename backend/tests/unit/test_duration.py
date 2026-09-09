"""Durées ISO 8601."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.duration import parse_duration


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("P1D", timedelta(days=1)),
        ("PT6H", timedelta(hours=6)),
        ("PT15M", timedelta(minutes=15)),
        ("P1DT6H", timedelta(days=1, hours=6)),
        ("PT90S", timedelta(seconds=90)),
    ],
)
def test_accepted(value, expected):
    assert parse_duration(value) == expected


@pytest.mark.parametrize("value", ["P", "PT", "", "1D", "jamais", "PT0S", None])
def test_rejected(value):
    with pytest.raises(ValueError):
        parse_duration(value)
