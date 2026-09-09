"""Comparaison de deux exécutions."""

from __future__ import annotations

from app.comparison.diff import RunSnapshot, compare


def field(name: str, data_type: str = "string", position: int = 0) -> dict:
    return {"column_name": name, "data_type": data_type, "nullable": True, "position": position}


def test_identical_runs_show_no_change():
    snapshot = RunSnapshot(
        rows=1000, score=100.0, schema=[field("a")], checks={"schema": "success"}
    )
    diff = compare(snapshot, snapshot)
    assert diff["rows_delta"] == 0
    assert diff["score_delta"] == 0.0
    assert diff["checks_diff"] == []
    assert diff["schema_diff"] == {"added": [], "removed": [], "renamed": [], "type_changed": []}


def test_volume_drop_is_quantified():
    diff = compare(RunSnapshot(rows=300, score=90.0), RunSnapshot(rows=1000, score=100.0))
    assert diff["rows_delta"] == -700
    assert diff["rows_delta_pct"] == -70.0
    assert diff["score_delta"] == -10.0


def test_added_column_is_reported():
    diff = compare(
        RunSnapshot(schema=[field("a", position=0), field("b", position=1)]),
        RunSnapshot(schema=[field("a", position=0)]),
    )
    assert diff["schema_diff"]["added"] == ["b"]


def test_type_change_is_reported():
    diff = compare(
        RunSnapshot(schema=[field("a", "string")]),
        RunSnapshot(schema=[field("a", "float")]),
    )
    assert diff["schema_diff"]["type_changed"] == [{"column": "a", "from": "float", "to": "string"}]


def test_check_status_changes_are_listed():
    diff = compare(
        RunSnapshot(checks={"schema": "warning", "types": "success"}),
        RunSnapshot(checks={"schema": "success", "types": "success"}),
    )
    assert diff["checks_diff"] == [{"check_name": "schema", "from": "success", "to": "warning"}]


def test_check_appearing_or_disappearing_is_a_change():
    """Un contrôle qui apparaît ou cesse d'être applicable est une information,
    pas un non-événement."""
    diff = compare(RunSnapshot(checks={"volume": "success"}), RunSnapshot(checks={}))
    assert diff["checks_diff"] == [{"check_name": "volume", "from": None, "to": "success"}]


def test_missing_values_do_not_produce_bogus_deltas():
    diff = compare(RunSnapshot(rows=None, score=None), RunSnapshot(rows=1000, score=100.0))
    assert diff["rows_delta"] is None
    assert diff["score_delta"] is None
