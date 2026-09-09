"""Tests d'intégration de l'API, contre une base PostgreSQL réelle."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.db

P = "/api/v1"
UNKNOWN = "00000000-0000-0000-0000-000000000000"


def upload(client, dataset, samples, name: str):
    with samples[name].open("rb") as handle:
        return client.post(
            f"{P}/runs/upload",
            data={"dataset_id": str(dataset.id)},
            files={"file": (f"{name}.csv", handle, "text/csv")},
        )


def test_health(client):
    response = client.get(f"{P}/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}


def test_create_source_and_dataset(client):
    source = client.post(
        f"{P}/sources",
        json={
            "name": "data.economie.gouv.fr",
            "url": "https://example.org/x.csv",
            "format": "csv",
            "license": "Licence Ouverte 2.0",
        },
    )
    assert source.status_code == 201

    dataset = client.post(
        f"{P}/datasets",
        json={
            "source_id": source.json()["id"],
            "name": "Un dataset",
            "expected_frequency": "PT6H",
            "config": {},
        },
    )
    assert dataset.status_code == 201
    assert dataset.json()["expected_frequency"] == "PT6H"
    assert dataset.json()["last_run"] is None


def test_dataset_on_unknown_source_is_404(client):
    response = client.post(f"{P}/datasets", json={"source_id": UNKNOWN, "name": "x"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "source_not_found"


def test_clean_run_scores_one_hundred(client, dataset, samples):
    response = upload(client, dataset, samples, "clean")
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "success"
    assert body["score"] == 100.0
    assert body["rows_read"] == 1000
    assert body["columns_read"] == 47
    assert body["checksum"].startswith("sha256:")
    assert body["freshness"]["origin"] == "column"
    assert len(body["schema"]) == 47
    assert body["comparison"] is None  # première exécution


def test_degraded_run_reports_the_right_check(client, dataset, samples):
    body = upload(client, dataset, samples, "duplicates_failed").json()
    assert body["status"] == "failed"
    uniqueness = next(r for r in body["results"] if r["check_name"] == "uniqueness")
    assert uniqueness["status"] == "failed"
    assert uniqueness["failed_count"] == 30
    assert uniqueness["details"]["sample_keys"]


def test_empty_file_fails_without_a_score(client, dataset, samples):
    """Un fichier vide donne un run en échec, pas un score flatteur."""
    body = upload(client, dataset, samples, "empty").json()
    assert body["status"] == "failed"
    assert body["score"] is None
    assert "empty_file" in body["error_message"]
    assert body["results"] == []


def test_second_run_produces_a_comparison(client, dataset, samples):
    upload(client, dataset, samples, "clean")
    second = upload(client, dataset, samples, "schema_added").json()

    comparison = second["comparison"]
    assert comparison is not None
    assert comparison["schema_diff"]["added"] == ["services_v2"]
    assert comparison["score_delta"] < 0
    assert {"check_name": "schema", "from": "success", "to": "warning"} in comparison["checks_diff"]


def test_comparison_endpoint_is_204_on_first_run(client, dataset, samples):
    run_id = upload(client, dataset, samples, "clean").json()["id"]
    assert client.get(f"{P}/runs/{run_id}/comparison").status_code == 204


def test_history_is_paginated_and_sorted(client, dataset, samples):
    for name in ("clean", "nulls_warning", "stale"):
        upload(client, dataset, samples, name)

    page = client.get(f"{P}/datasets/{dataset.id}/runs?limit=2&offset=0").json()
    assert page["total"] == 3
    assert len(page["items"]) == 2
    assert page["items"][0]["started_at"] >= page["items"][1]["started_at"]


def test_sub_resources(client, dataset, samples):
    run_id = upload(client, dataset, samples, "clean").json()["id"]

    results = client.get(f"{P}/runs/{run_id}/results").json()
    assert {r["check_name"] for r in results} >= {
        "schema",
        "types",
        "uniqueness",
        "completeness",
        "ranges",
        "freshness",
        "volume",
        "consistency",
    }
    assert len(client.get(f"{P}/runs/{run_id}/schema").json()) == 47

    report = client.get(f"{P}/runs/{run_id}/report")
    assert report.status_code == 200
    assert "attachment" in report.headers["content-disposition"]
    assert report.json()["score"] == 100.0


def test_weights_are_copied_into_each_result(client, dataset, samples):
    """Un run doit rester explicable même si la configuration change ensuite."""
    body = upload(client, dataset, samples, "clean").json()
    weights = {r["check_name"]: r["weight"] for r in body["results"]}
    assert weights["schema"] == 3
    assert weights["volume"] == 1


def test_dataset_list_shows_the_last_run(client, dataset, samples):
    upload(client, dataset, samples, "nulls_failed")
    entry = next(d for d in client.get(f"{P}/datasets").json() if d["id"] == str(dataset.id))
    assert entry["last_run"]["status"] == "warning"


def test_patch_dataset(client, dataset):
    response = client.patch(f"{P}/datasets/{dataset.id}", json={"expected_frequency": "PT6H"})
    assert response.status_code == 200
    assert response.json()["expected_frequency"] == "PT6H"


@pytest.mark.parametrize(
    ("method", "path", "payload", "expected"),
    [
        ("get", f"/runs/{UNKNOWN}", None, 404),
        ("get", f"/datasets/{UNKNOWN}", None, 404),
        ("get", f"/datasets/{UNKNOWN}/runs", None, 404),
        ("post", "/runs", {"dataset_id": UNKNOWN}, 404),
        ("post", "/datasets", {"name": "sans source"}, 422),
        ("post", "/sources", {"name": "x", "url": "http://pas-https.org/a.csv"}, 422),
    ],
)
def test_error_envelope(client, method, path, payload, expected):
    response = getattr(client, method)(f"{P}{path}", **({"json": payload} if payload else {}))
    assert response.status_code == expected
    body = response.json()
    assert set(body["error"]) == {"code", "message", "details"}


def test_pagination_bounds(client, dataset):
    assert client.get(f"{P}/datasets/{dataset.id}/runs?limit=500").status_code == 422
    assert client.get(f"{P}/datasets/{dataset.id}/runs?limit=0").status_code == 422
