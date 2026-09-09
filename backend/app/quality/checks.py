"""Les huit contrôles de qualité de DataGuard.

Principe commun : chaque colonne concernée est évaluée pour elle-même, puis les
statuts sont agrégés au plus grave. Un pourcentage calculé sur l'ensemble du
fichier diluerait une colonne entièrement cassée dans la masse des colonnes
saines et la ferait ressortir en simple alerte.

`failed_count` compte des éléments dont l'unité dépend du contrôle ; elle est
précisée dans `details["unit"]`.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.core.duration import parse_duration
from app.profiling.schema import conversion_failures, diff_schemas
from app.quality.base import (
    CheckContext,
    CheckResult,
    Status,
    coverage,
    coverage_details,
    pct,
    sample,
    status_from_pct,
    worst,
)


def _threshold(ctx: CheckContext, key: str, fallback: float) -> float:
    return float(ctx.defaults.get(key, fallback))


# ---------------------------------------------------------------------------


class CompletenessCheck:
    name = "completeness"
    dimension = "Complétude"

    def run(self, ctx: CheckContext) -> CheckResult:
        rows = len(ctx.df)
        columns: list[dict[str, Any]] = []
        statuses: list[Status] = []
        configured, missing = coverage(
            ctx,
            lambda r: bool(r.get("required") or "null_warn_pct" in r or "null_fail_pct" in r),
        )

        for column, rules in ctx.columns_config.items():
            constrained = (
                rules.get("required") or "null_warn_pct" in rules or "null_fail_pct" in rules
            )
            if not constrained or not ctx.present(column):
                continue

            nulls = int(ctx.df[column].isna().sum())
            null_pct = pct(nulls, rows)

            if rules.get("required"):
                # Une colonne obligatoire ne tolère aucune absence.
                status = Status.FAILED if nulls else Status.SUCCESS
                warn, fail = 0.0, 0.0
            else:
                warn = float(rules.get("null_warn_pct", _threshold(ctx, "null_warn_pct", 5.0)))
                fail = float(rules.get("null_fail_pct", _threshold(ctx, "null_fail_pct", 20.0)))
                status = status_from_pct(null_pct, warn, fail)

            statuses.append(status)
            if status is not Status.SUCCESS:
                columns.append(
                    {
                        "column": column,
                        "null_count": nulls,
                        "null_pct": null_pct,
                        "status": status.value,
                        "required": bool(rules.get("required")),
                        "warn_pct": warn,
                        "fail_pct": fail,
                    }
                )

        if not statuses:
            return CheckResult(
                self.name,
                self.dimension,
                Status.SKIPPED,
                ctx.weight_of(self.name),
                details={"reason": "aucune colonne ne déclare de contrainte de complétude"},
            )

        return CheckResult(
            self.name,
            self.dimension,
            worst(statuses),
            ctx.weight_of(self.name),
            failed_count=len(columns),
            threshold={
                "null_warn_pct": _threshold(ctx, "null_warn_pct", 5.0),
                "null_fail_pct": _threshold(ctx, "null_fail_pct", 20.0),
            },
            details={
                "unit": "colonnes en défaut",
                **coverage_details(configured, missing),
                "columns": columns,
            },
        )


class UniquenessCheck:
    name = "uniqueness"
    dimension = "Unicité"

    def run(self, ctx: CheckContext) -> CheckResult:
        keys = ctx.config.get("key_columns", [])
        missing = [k for k in keys if not ctx.present(k)]
        if not keys or missing:
            reason = (
                "aucune clé déclarée"
                if not keys
                else f"colonnes clés absentes : {', '.join(missing)}"
            )
            return CheckResult(
                self.name,
                self.dimension,
                Status.SKIPPED,
                ctx.weight_of(self.name),
                details={"reason": reason},
            )

        rows = len(ctx.df)
        duplicated = ctx.df.duplicated(subset=keys, keep="first")
        count = int(duplicated.sum())
        ratio = pct(count, rows)
        warn = _threshold(ctx, "duplicate_warn_pct", 0.0)
        fail = _threshold(ctx, "duplicate_fail_pct", 0.1)

        offenders = ctx.df.loc[duplicated, keys[0]].tolist() if count else []
        return CheckResult(
            self.name,
            self.dimension,
            status_from_pct(ratio, warn, fail),
            ctx.weight_of(self.name),
            failed_count=count,
            threshold={"warn_pct": warn, "fail_pct": fail},
            details={
                "unit": "lignes en doublon",
                "key_columns": keys,
                "duplicate_pct": ratio,
                "sample_keys": sample(offenders),
            },
        )


class TypesCheck:
    name = "types"
    dimension = "Validité (type)"

    def run(self, ctx: CheckContext) -> CheckResult:
        warn = _threshold(ctx, "type_warn_pct", 0.0)
        fail = _threshold(ctx, "type_fail_pct", 1.0)
        columns: list[dict[str, Any]] = []
        statuses: list[Status] = []
        total = 0
        configured, missing = coverage(ctx, lambda r: r.get("type") not in (None, "string"))

        for column, rules in ctx.columns_config.items():
            declared = rules.get("type")
            if declared in (None, "string") or not ctx.present(column):
                continue

            series = ctx.df[column]
            non_null = int(series.notna().sum())
            if non_null == 0:
                continue

            failures = conversion_failures(series, declared)
            count = int(failures.sum())
            ratio = pct(count, non_null)
            status = status_from_pct(ratio, warn, fail)
            statuses.append(status)
            total += count

            if status is not Status.SUCCESS:
                bad = series[failures].tolist()
                columns.append(
                    {
                        "column": column,
                        "declared_type": declared,
                        "invalid_count": count,
                        "invalid_pct": ratio,
                        "status": status.value,
                        "sample_values": sample(bad),
                    }
                )

        if not statuses:
            return CheckResult(
                self.name,
                self.dimension,
                Status.SKIPPED,
                ctx.weight_of(self.name),
                details={"reason": "aucune colonne typée à contrôler"},
            )

        return CheckResult(
            self.name,
            self.dimension,
            worst(statuses),
            ctx.weight_of(self.name),
            failed_count=total,
            threshold={"warn_pct": warn, "fail_pct": fail},
            details={
                "unit": "valeurs non convertibles",
                **coverage_details(configured, missing),
                "columns": columns,
            },
        )


class RangesCheck:
    name = "ranges"
    dimension = "Validité (plage)"

    def run(self, ctx: CheckContext) -> CheckResult:
        warn = _threshold(ctx, "range_warn_pct", 0.0)
        fail = _threshold(ctx, "range_fail_pct", 1.0)
        columns: list[dict[str, Any]] = []
        statuses: list[Status] = []
        total = 0
        configured, missing = coverage(
            ctx, lambda r: bool({"min", "max", "allowed_values", "pattern"} & r.keys())
        )

        for column, rules in ctx.columns_config.items():
            constrained = {"min", "max", "allowed_values", "pattern"} & rules.keys()
            if not constrained or not ctx.present(column):
                continue

            series = ctx.df[column]
            non_null = series.dropna()
            if non_null.empty:
                continue

            if "min" in rules or "max" in rules:
                numeric = pd.to_numeric(non_null, errors="coerce")
                # Les valeurs non convertibles relèvent du contrôle de type ;
                # les compter ici les ferait sanctionner deux fois.
                violating = pd.Series(False, index=non_null.index)
                if "min" in rules:
                    violating |= numeric.notna() & (numeric < rules["min"])
                if "max" in rules:
                    violating |= numeric.notna() & (numeric > rules["max"])
            elif "allowed_values" in rules:
                violating = ~non_null.isin(rules["allowed_values"])
            else:
                violating = ~non_null.astype(str).str.match(rules["pattern"])

            count = int(violating.sum())
            ratio = pct(count, len(non_null))
            status = status_from_pct(ratio, warn, fail)
            statuses.append(status)
            total += count

            if status is not Status.SUCCESS:
                rule = {
                    k: rules[k] for k in ("min", "max", "allowed_values", "pattern") if k in rules
                }
                columns.append(
                    {
                        "column": column,
                        "rule": rule,
                        "invalid_count": count,
                        "invalid_pct": ratio,
                        "status": status.value,
                        "sample_values": sample(non_null[violating].tolist()),
                    }
                )

        if not statuses:
            return CheckResult(
                self.name,
                self.dimension,
                Status.SKIPPED,
                ctx.weight_of(self.name),
                details={"reason": "aucune plage déclarée"},
            )

        return CheckResult(
            self.name,
            self.dimension,
            worst(statuses),
            ctx.weight_of(self.name),
            failed_count=total,
            threshold={"warn_pct": warn, "fail_pct": fail},
            details={
                "unit": "valeurs hors bornes",
                **coverage_details(configured, missing),
                "columns": columns,
            },
        )


class FreshnessCheck:
    name = "freshness"
    dimension = "Fraîcheur"

    def run(self, ctx: CheckContext) -> CheckResult:
        settings = ctx.config.get("freshness", {})
        columns = [c for c in settings.get("columns", []) if ctx.present(c)]

        # Ordre de priorité : une date portée par la donnée l'emporte toujours
        # sur une date de transport. Un fichier régénéré chaque nuit avec de
        # vieilles données est frais au sens du fichier, périmé au sens utile.
        latest: pd.Timestamp | None = None
        for column in columns:
            parsed = pd.to_datetime(
                ctx.df[column], errors="coerce", utc=True, format="ISO8601"
            ).max()
            if pd.notna(parsed):
                latest = parsed if latest is None else max(latest, parsed)
        origin = "column"

        if latest is None and ctx.fallback_freshness:
            fallback_date, origin = ctx.fallback_freshness
            latest = pd.Timestamp(fallback_date).tz_convert("UTC")

        if latest is None:
            return CheckResult(
                self.name,
                self.dimension,
                Status.SKIPPED,
                ctx.weight_of(self.name),
                details={
                    "reason": "aucune date exploitable, ni dans la donnée "
                    "ni dans les métadonnées du fichier",
                    "origin": "none",
                },
            )

        frequency = parse_duration(settings.get("expected_frequency", "P1D"))
        age = pd.Timestamp(ctx.now).tz_convert("UTC") - latest
        age_hours = round(age.total_seconds() / 3600, 2)

        if age <= frequency * 1.5:
            status = Status.SUCCESS
        elif age <= frequency * 3:
            status = Status.WARNING
        else:
            status = Status.FAILED

        return CheckResult(
            self.name,
            self.dimension,
            status,
            ctx.weight_of(self.name),
            failed_count=0 if status is Status.SUCCESS else 1,
            threshold={
                "expected_frequency": settings.get("expected_frequency", "P1D"),
                "warn_after_hours": round(frequency.total_seconds() / 3600 * 1.5, 2),
                "fail_after_hours": round(frequency.total_seconds() / 3600 * 3, 2),
            },
            details={
                "unit": "dataset",
                "freshness_date": latest.isoformat(),
                "origin": origin,
                # Nom distinct de `columns`, réservé aux listes d'objets décrivant
                # une anomalie par colonne : la même clé portant deux formes
                # différentes, l'affichage ne pouvait pas les distinguer.
                "source_columns": columns,
                "age_hours": age_hours,
            },
        )


class VolumeCheck:
    name = "volume"
    dimension = "Volume"

    def run(self, ctx: CheckContext) -> CheckResult:
        rows = len(ctx.df)
        settings = ctx.config.get("volume", {})
        warn = float(settings.get("warn_pct", 10.0))
        fail = float(settings.get("fail_pct", 50.0))

        if rows == 0:
            return CheckResult(
                self.name,
                self.dimension,
                Status.FAILED,
                ctx.weight_of(self.name),
                failed_count=1,
                threshold={"warn_pct": warn, "fail_pct": fail},
                details={"unit": "dataset", "rows": 0, "reason": "fichier sans aucune ligne"},
            )

        if ctx.previous_rows is None:
            return CheckResult(
                self.name,
                self.dimension,
                Status.SKIPPED,
                ctx.weight_of(self.name),
                details={
                    "unit": "dataset",
                    "rows": rows,
                    "reason": "aucune exécution précédente pour comparer",
                },
            )

        delta = rows - ctx.previous_rows
        variation = abs(pct(abs(delta), ctx.previous_rows))
        return CheckResult(
            self.name,
            self.dimension,
            status_from_pct(variation, warn, fail),
            ctx.weight_of(self.name),
            failed_count=0 if variation <= warn else 1,
            threshold={"warn_pct": warn, "fail_pct": fail},
            details={
                "unit": "dataset",
                "rows": rows,
                "previous_rows": ctx.previous_rows,
                "delta": delta,
                "variation_pct": variation,
            },
        )


class SchemaCheck:
    name = "schema"
    dimension = "Schéma"

    def run(self, ctx: CheckContext) -> CheckResult:
        reference = ctx.reference_schema
        if not reference or not reference.get("fields"):
            return CheckResult(
                self.name,
                self.dimension,
                Status.SKIPPED,
                ctx.weight_of(self.name),
                details={"reason": "aucun schéma de référence enregistré"},
            )

        diff = diff_schemas(reference["fields"], ctx.observed_schema)
        added = diff["added"]
        removed = diff["removed"]
        renamed = diff["renamed"]
        type_changed = diff["type_changed"]

        if removed or renamed or type_changed:
            status = Status.FAILED
        elif added:
            status = Status.WARNING
        else:
            status = Status.SUCCESS

        return CheckResult(
            self.name,
            self.dimension,
            status,
            ctx.weight_of(self.name),
            failed_count=len(removed) + len(added) + len(renamed) + len(type_changed),
            threshold={
                "added": "warning",
                "removed": "failed",
                "renamed": "failed",
                "type_changed": "failed",
            },
            details={
                "unit": "différences de schéma",
                "added": added,
                "removed": removed,
                "renamed": renamed,
                "type_changed": type_changed,
                "reference_columns": len(reference["fields"]),
                "observed_columns": len(ctx.observed_schema),
            },
        )


class ConsistencyCheck:
    name = "consistency"
    dimension = "Cohérence"

    def run(self, ctx: CheckContext) -> CheckResult:
        rules = ctx.config.get("consistency", {}).get("rules", [])
        if not rules:
            return CheckResult(
                self.name,
                self.dimension,
                Status.SKIPPED,
                ctx.weight_of(self.name),
                details={"reason": "aucune règle de cohérence déclarée"},
            )

        warn = _threshold(ctx, "consistency_warn_pct", 0.0)
        fail = _threshold(ctx, "consistency_fail_pct", 1.0)
        statuses: list[Status] = []
        reported: list[dict[str, Any]] = []
        total = 0

        for rule in rules:
            if rule.get("type") != "not_in_future":
                continue
            tolerance = parse_duration(rule.get("tolerance", "PT0S"))
            limit = pd.Timestamp(ctx.now).tz_convert("UTC") + tolerance
            columns = [c for c in rule.get("columns", []) if ctx.present(c)]
            if not columns:
                continue

            count = 0
            examples: list[Any] = []
            checked = 0
            for column in columns:
                parsed = pd.to_datetime(ctx.df[column], errors="coerce", utc=True, format="ISO8601")
                checked += int(parsed.notna().sum())
                violating = parsed.notna() & (parsed > limit)
                count += int(violating.sum())
                if violating.any() and len(examples) < 5:
                    examples.extend(ctx.df.loc[violating, column].head(5).tolist())

            if checked == 0:
                continue
            ratio = pct(count, checked)
            status = status_from_pct(ratio, warn, fail)
            statuses.append(status)
            total += count
            if status is not Status.SUCCESS:
                reported.append(
                    {
                        "rule": rule.get("name"),
                        "description": rule.get("description"),
                        "invalid_count": count,
                        "invalid_pct": ratio,
                        "status": status.value,
                        "tolerance": rule.get("tolerance"),
                        "sample_values": sample(examples),
                    }
                )

        if not statuses:
            return CheckResult(
                self.name,
                self.dimension,
                Status.SKIPPED,
                ctx.weight_of(self.name),
                details={"reason": "aucune règle applicable aux colonnes présentes"},
            )

        return CheckResult(
            self.name,
            self.dimension,
            worst(statuses),
            ctx.weight_of(self.name),
            failed_count=total,
            threshold={"warn_pct": warn, "fail_pct": fail},
            details={"unit": "valeurs incohérentes", "rules": reported},
        )


# Ordre d'exécution : il n'a pas d'incidence sur le résultat, mais il fixe
# l'ordre d'affichage dans le dashboard.
ALL_CHECKS: list[Any] = [
    SchemaCheck(),
    TypesCheck(),
    UniquenessCheck(),
    CompletenessCheck(),
    RangesCheck(),
    FreshnessCheck(),
    VolumeCheck(),
    ConsistencyCheck(),
]
