"""Relevé et comparaison de schémas."""

from __future__ import annotations

import pandas as pd

from app.profiling.schema import diff_schemas, infer_type, observe_schema


def test_declared_type_is_kept_when_values_convert():
    series = pd.Series(["1.5", "2.5", "3.5"])
    assert infer_type(series, "float") == "float"


def test_declared_type_is_abandoned_when_values_do_not_convert():
    """Une colonne de nombres passée à la virgule décimale n'est plus numérique :
    c'est précisément le signal que le contrôle de schéma doit remonter."""
    series = pd.Series(["1,5", "2,5", "3,5"])
    assert infer_type(series, "float") == "string"


def test_a_few_bad_values_do_not_change_the_type():
    series = pd.Series(["1.5"] * 99 + ["n/a"])
    assert infer_type(series, "float") == "float"


def test_empty_column_keeps_its_declaration():
    """Aucune valeur ne contredit la déclaration : signaler un changement de
    type ici serait un faux positif."""
    assert infer_type(pd.Series([None, None], dtype=object), "float") == "float"


def test_observed_schema_follows_column_order():
    frame = pd.DataFrame({"b": ["1"], "a": ["x"]})
    observed = observe_schema(frame, {"columns": {"b": {"type": "float"}}})
    assert [f["column_name"] for f in observed] == ["b", "a"]
    assert [f["position"] for f in observed] == [0, 1]
    assert observed[0]["data_type"] == "float"
    assert observed[1]["data_type"] == "string"


def field(name, data_type="string", position=0):
    return {"column_name": name, "data_type": data_type, "nullable": True, "position": position}


def test_rename_detected_at_identical_position():
    diff = diff_schemas([field("old", position=0)], [field("new", position=0)])
    assert diff["renamed"] == [{"from": "old", "to": "new"}]
    assert diff["added"] == [] and diff["removed"] == []


def test_unrelated_positions_are_not_a_rename():
    diff = diff_schemas(
        [field("old", position=0), field("keep", position=1)],
        [field("keep", position=0), field("new", position=1)],
    )
    assert diff["renamed"] == []
    assert diff["removed"] == ["old"] and diff["added"] == ["new"]
