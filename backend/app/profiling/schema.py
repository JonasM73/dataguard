"""Relevé du schéma observé d'un DataFrame.

Le type observé n'est pas le dtype brut de Pandas : un CSV lu en texte donnerait
partout `object`, ce qui ne dirait rien. On confronte donc chaque colonne au type
que la configuration déclare, et on retient ce type si les valeurs s'y
convertissent effectivement. Une colonne déclarée `float` dont les valeurs
passent à la virgule décimale bascule ainsi en `string`, et le contrôle de schéma
la signale comme changée — ce qui est exactement le signal recherché.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

# Part minimale de valeurs non nulles devant se convertir pour que le type
# déclaré soit retenu. En dessous, la colonne est considérée comme du texte.
CONVERSION_RATIO = 0.9


def convert(series: pd.Series, target: str) -> pd.Series:
    """Convertit une série vers un type cible ; les échecs deviennent NaT/NaN."""
    if target == "float":
        return pd.to_numeric(series, errors="coerce")
    if target == "integer":
        return pd.to_numeric(series, errors="coerce").astype("Int64", errors="ignore")
    if target == "datetime":
        return pd.to_datetime(series, errors="coerce", utc=True, format="ISO8601")
    return series


def conversion_failures(series: pd.Series, target: str) -> pd.Series:
    """Masque booléen des valeurs non nulles que le type cible rejette."""
    if target in ("string", None):
        return pd.Series(False, index=series.index)
    converted = convert(series, target)
    return series.notna() & converted.isna()


def infer_type(series: pd.Series, declared: str | None) -> str:
    """Type observé d'une colonne, au regard du type déclaré."""
    if declared in (None, "string"):
        return "string"
    non_null = series.dropna()
    if non_null.empty:
        # Aucune valeur : rien ne contredit la déclaration, on la conserve pour
        # ne pas signaler un faux changement de schéma sur une colonne vide.
        return declared
    ok = (~conversion_failures(non_null, declared)).sum()
    return declared if ok / len(non_null) >= CONVERSION_RATIO else "string"


def diff_schemas(
    reference: list[dict[str, Any]], observed: list[dict[str, Any]]
) -> dict[str, list[Any]]:
    """Compare deux schémas et rend les colonnes ajoutées, supprimées, renommées
    et changées de type.

    Une colonne disparue et une colonne apparue à la même position sont traitées
    comme un renommage : les signaler comme une suppression doublée d'un ajout
    ferait croire à une perte de donnée là où il n'y a qu'un changement de nom.
    """
    ref = {f["column_name"]: f for f in reference}
    obs = {f["column_name"]: f for f in observed}

    removed = [c for c in ref if c not in obs]
    added = [c for c in obs if c not in ref]
    type_changed = [
        {"column": c, "from": ref[c]["data_type"], "to": obs[c]["data_type"]}
        for c in ref
        if c in obs and ref[c]["data_type"] != obs[c]["data_type"]
    ]

    renamed: list[dict[str, str]] = []
    for old in list(removed):
        for new in list(added):
            if ref[old]["position"] == obs[new]["position"]:
                renamed.append({"from": old, "to": new})
                removed.remove(old)
                added.remove(new)
                break

    return {"added": added, "removed": removed, "renamed": renamed, "type_changed": type_changed}


def observe_schema(df: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, Any]]:
    """Schéma observé, dans l'ordre des colonnes du fichier."""
    columns_config = config.get("columns", {})
    fields: list[dict[str, Any]] = []
    for position, column in enumerate(df.columns):
        declared = columns_config.get(column, {}).get("type")
        fields.append(
            {
                "column_name": column,
                "data_type": infer_type(df[column], declared),
                "nullable": bool(df[column].isna().any()),
                "position": position,
            }
        )
    return fields
