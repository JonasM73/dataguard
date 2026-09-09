"""Le moteur de contrôles, éprouvé sur les jeux de données dégradés.

Chaque fichier synthétique ne porte qu'une seule famille d'anomalie. Un test
vérifie donc deux choses à la fois : que le contrôle visé réagit bien, et
qu'aucun autre ne se déclenche. Le second point compte autant que le premier —
un moteur qui alerte sur tout n'aide pas davantage qu'un moteur muet.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.profiling.schema import observe_schema
from app.quality.base import CheckContext, Status
from app.quality.engine import run_checks

# fichier -> (contrôle visé, statut attendu, statut global, contrôles qui ont
# légitimement le droit de dévier en plus)
MATRIX: dict[str, tuple[str, str, str, set[str]]] = {
    "clean": ("", "success", "success", set()),
    "nulls_warning": ("completeness", "warning", "warning", set()),
    "nulls_failed": ("completeness", "failed", "warning", set()),
    "duplicates_warning": ("uniqueness", "warning", "warning", set()),
    "duplicates_failed": ("uniqueness", "failed", "failed", set()),
    "types_failed": ("types", "failed", "failed", set()),
    "ranges_warning": ("ranges", "warning", "warning", set()),
    "ranges_failed": ("ranges", "failed", "warning", set()),
    "stale": ("freshness", "failed", "warning", set()),
    "schema_added": ("schema", "warning", "warning", set()),
    "schema_removed": ("schema", "failed", "failed", set()),
    "schema_renamed": ("schema", "failed", "failed", set()),
    # Une latitude passée à la virgule décimale casse le type ET le schéma :
    # les deux signaux sont justes, il n'y a pas de doublon à corriger.
    "schema_type_changed": ("schema", "failed", "failed", {"types"}),
    "volume_warning": ("volume", "warning", "warning", set()),
    "volume_failed": ("volume", "failed", "warning", set()),
    "consistency": ("consistency", "warning", "warning", set()),
}

PREVIOUS_ROWS = 1000


def build_context(frame, config, reference_schema, now, **overrides) -> CheckContext:
    defaults = {
        "df": frame,
        "config": config,
        "now": now,
        "reference_schema": reference_schema,
        "previous_rows": PREVIOUS_ROWS,
        "observed_schema": observe_schema(frame, config),
    }
    defaults.update(overrides)
    return CheckContext(**defaults)


@pytest.mark.parametrize("name", list(MATRIX))
def test_sample_triggers_expected_check(name, read_sample, config, reference_schema, now):
    target, expected_check, expected_global, tolerated = MATRIX[name]
    report = run_checks(build_context(read_sample(name), config, reference_schema, now))

    assert report.status.value == expected_global, (
        f"{name} : statut global {report.status.value}, attendu {expected_global}"
    )

    if target:
        result = report.by_name(target)
        assert result is not None
        assert result.status.value == expected_check, (
            f"{name} : {target} rend {result.status.value}, attendu {expected_check}"
        )
        assert result.failed_count > 0, f"{name} : {target} ne compte aucune anomalie"

    deviating = {
        r.check_name
        for r in report.results
        if r.check_name != target and r.status not in (Status.SUCCESS, Status.SKIPPED)
    }
    assert deviating <= tolerated, f"{name} : contrôles déclenchés à tort : {deviating - tolerated}"


def test_clean_scores_one_hundred(read_sample, config, reference_schema, now):
    report = run_checks(build_context(read_sample("clean"), config, reference_schema, now))
    assert report.score == 100.0
    assert all(r.status in (Status.SUCCESS, Status.SKIPPED) for r in report.results), [
        r.check_name for r in report.results if r.status is not Status.SUCCESS
    ]


def test_volume_skipped_without_previous_run(read_sample, config, reference_schema, now):
    """Sans exécution précédente, le volume n'est pas comparable : il est écarté
    du score plutôt que compté comme un échec."""
    report = run_checks(
        build_context(read_sample("clean"), config, reference_schema, now, previous_rows=None)
    )
    assert report.by_name("volume").status is Status.SKIPPED
    assert report.score == 100.0


def test_schema_skipped_without_reference(read_sample, config, now):
    """Le premier run d'un dataset n'a rien à quoi se comparer."""
    report = run_checks(build_context(read_sample("clean"), config, None, now))
    assert report.by_name("schema").status is Status.SKIPPED


def test_schema_diff_names_the_renamed_column(read_sample, config, reference_schema, now):
    report = run_checks(build_context(read_sample("schema_renamed"), config, reference_schema, now))
    details = report.by_name("schema").details
    assert details["renamed"] == [{"from": "Prix SP95", "to": "Prix sans-plomb 95"}]
    # Un renommage ne doit pas être présenté comme une perte doublée d'un ajout.
    assert details["removed"] == [] and details["added"] == []


def test_details_carry_the_offending_values(read_sample, config, reference_schema, now):
    report = run_checks(build_context(read_sample("types_failed"), config, reference_schema, now))
    columns = report.by_name("types").details["columns"]
    assert columns[0]["column"] == "Prix Gazole"
    assert "n/a" in columns[0]["sample_values"]


def test_freshness_reports_its_origin(read_sample, config, reference_schema, now):
    report = run_checks(build_context(read_sample("clean"), config, reference_schema, now))
    assert report.by_name("freshness").details["origin"] == "column"


def test_freshness_falls_back_to_file_metadata(read_sample, config, reference_schema, now):
    """Sans colonne de date exploitable, on se rabat sur la date du fichier —
    en le disant, parce que c'est un signal moins fiable."""
    frame = read_sample("clean").drop(columns=list(config["freshness"]["columns"]))
    report = run_checks(
        build_context(
            frame,
            config,
            reference_schema,
            now,
            fallback_freshness=(datetime(2026, 9, 9, 6, 0, tzinfo=UTC), "http_header"),
        )
    )
    freshness = report.by_name("freshness")
    assert freshness.status is Status.SUCCESS
    assert freshness.details["origin"] == "http_header"


def test_stale_file_is_reported_as_failed(read_sample, config, reference_schema, now):
    report = run_checks(build_context(read_sample("stale"), config, reference_schema, now))
    freshness = report.by_name("freshness")
    assert freshness.status is Status.FAILED
    assert freshness.details["age_hours"] > 72  # trois fois la fréquence attendue


def test_missing_columns_are_reported_not_silently_ignored(
    read_sample, config, reference_schema, now
):
    """Un contrôle qui ne trouve pas ses colonnes doit le dire.

    Sans cela, un fichier dont les colonnes ont été renommées ressort
    « conforme » alors que le contrôle n'a presque rien regardé — le faux
    acquittement que l'outil est censé empêcher. Cas rencontré pour de vrai :
    la source s'exporte sous deux nommages de colonnes différents.
    """
    frame = read_sample("clean").rename(
        columns={"Prix Gazole": "gazole_prix", "Ville": "ville", "Code postal": "cp"}
    )
    report = run_checks(build_context(frame, config, reference_schema, now))

    completeness = report.by_name("completeness").details
    assert completeness["checked_columns"] < completeness["configured_columns"]
    assert set(completeness["missing_columns"]) == {"Code postal", "Ville", "Prix Gazole"}

    ranges = report.by_name("ranges").details
    assert "Prix Gazole" in ranges["missing_columns"]


def test_coverage_is_complete_on_an_intact_file(read_sample, config, reference_schema, now):
    report = run_checks(build_context(read_sample("clean"), config, reference_schema, now))
    for name in ("completeness", "types", "ranges"):
        details = report.by_name(name).details
        assert details["missing_columns"] == []
        assert details["checked_columns"] == details["configured_columns"]


def test_freshness_columns_do_not_collide_with_per_column_findings(
    read_sample, config, reference_schema, now
):
    """`columns` ne porte que des objets décrivant une anomalie par colonne.

    La fraîcheur y publiait une simple liste de noms, et l'affichage — qui
    attend des objets — en tirait un tableau de lignes vides.
    """
    report = run_checks(build_context(read_sample("clean"), config, reference_schema, now))
    freshness = report.by_name("freshness").details
    assert "columns" not in freshness
    assert freshness["source_columns"] == config["freshness"]["columns"]


def test_data_dated_in_the_future_is_fresh_but_inconsistent(
    read_sample, config, reference_schema, now
):
    """Séparation assumée : la fraîcheur mesure l'ancienneté, la cohérence la
    vraisemblance. Une donnée horodatée dans le futur est récente — et suspecte."""
    report = run_checks(build_context(read_sample("consistency"), config, reference_schema, now))
    assert report.by_name("freshness").status is Status.SUCCESS
    assert report.by_name("consistency").status is Status.WARNING
