"""Ingestion : garde-fous et lecture."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ingestion.loader import IngestionError, fetch_local, read_table


def test_reads_a_valid_file(samples, config):
    frame = read_table(samples["clean"], config)
    assert len(frame) == 1000
    assert len(frame.columns) == 47


def test_empty_file_is_rejected(samples, config):
    """Un fichier vide n'a pas une qualité médiocre : il n'a pas de qualité du
    tout. Le laisser passer produirait un score flatteur et trompeur."""
    with pytest.raises(IngestionError) as excinfo:
        read_table(samples["empty"], config)
    assert excinfo.value.code == "empty_file"


def test_postal_codes_keep_their_leading_zero(samples, config):
    """Lire en texte n'est pas un détail : en numérique, 06110 deviendrait 6110."""
    frame = read_table(samples["clean"], config)
    assert frame["Code postal"].str.len().eq(5).all()


def test_types_are_not_guessed(samples, config):
    """Laisser Pandas inférer masquerait ce que le contrôle de type doit voir.

    On vérifie que les valeurs restent du texte, sans se lier au dtype exact :
    Pandas 2 rend `object` là où Pandas 3 rend `str`, et le projet doit
    fonctionner avec les deux."""
    frame = read_table(samples["types_failed"], config)
    values = frame["Prix Gazole"].dropna()
    assert values.map(type).eq(str).all()
    assert "n/a" in values.tolist()


def test_missing_file(tmp_path):
    with pytest.raises(IngestionError) as excinfo:
        fetch_local(tmp_path / "absent.csv", tmp_path / "out.csv", 1_000_000)
    assert excinfo.value.code == "file_not_found"


def test_file_above_the_size_limit_is_refused(samples, tmp_path):
    with pytest.raises(IngestionError) as excinfo:
        fetch_local(samples["clean"], tmp_path / "out.csv", max_bytes=10)
    assert excinfo.value.code == "file_too_large"


def test_checksum_is_stable_and_sensitive(samples, tmp_path):
    first = fetch_local(samples["clean"], tmp_path / "a.csv", 100_000_000)
    second = fetch_local(samples["clean"], tmp_path / "b.csv", 100_000_000)
    assert first.checksum == second.checksum

    altered = Path(tmp_path / "altered.csv")
    altered.write_bytes(samples["clean"].read_bytes() + b"x")
    third = fetch_local(altered, tmp_path / "c.csv", 100_000_000)
    assert third.checksum != first.checksum


def test_plain_http_is_refused_before_any_request(tmp_path):
    """Le schéma est vérifié avant l'appel réseau : le test ne touche donc
    jamais à Internet."""
    from app.ingestion.loader import fetch_url

    with pytest.raises(IngestionError) as excinfo:
        fetch_url("http://example.org/data.csv", tmp_path / "out.csv", 1_000_000)
    assert excinfo.value.code == "insecure_url"
