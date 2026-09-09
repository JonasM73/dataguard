"""Récupération et lecture d'une source.

Trois garde-fous, dans cet ordre : le schéma d'URL est vérifié avant tout appel
réseau, la taille est contrôlée pendant le téléchargement (et non après, sinon
la limite ne protège de rien), et un fichier sans aucune ligne est rejeté avant
que les contrôles ne tournent — un fichier vide n'a pas une qualité de 89 %, il
n'a pas de qualité du tout.
"""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

CHUNK = 64 * 1024


class IngestionError(Exception):
    """Échec d'ingestion assorti d'un code exploitable par l'API."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class FetchedFile:
    path: Path
    size_bytes: int
    checksum: str
    origin: str  # "url" ou "local"
    last_modified: datetime | None = None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def fetch_url(url: str, destination: Path, max_bytes: int, timeout: float = 60.0) -> FetchedFile:
    """Télécharge une URL en refusant tout ce qui dépasse la limite de taille."""
    if not url.lower().startswith("https://"):
        raise IngestionError(
            "insecure_url",
            "Seules les URL https sont acceptées ; reçu : "
            f"{url.split('://', 1)[0] if '://' in url else url}",
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    last_modified: datetime | None = None

    try:
        with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as response:
            response.raise_for_status()

            declared = response.headers.get("content-length")
            if declared and int(declared) > max_bytes:
                raise IngestionError(
                    "file_too_large",
                    f"La source annonce {int(declared)} octets, au-delà de la limite "
                    f"de {max_bytes} octets.",
                )
            if header := response.headers.get("last-modified"):
                try:
                    last_modified = parsedate_to_datetime(header).astimezone(UTC)
                except (TypeError, ValueError):
                    last_modified = None

            with destination.open("wb") as handle:
                for chunk in response.iter_bytes(CHUNK):
                    written += len(chunk)
                    if written > max_bytes:
                        handle.close()
                        destination.unlink(missing_ok=True)
                        raise IngestionError(
                            "file_too_large",
                            f"Le téléchargement dépasse la limite de {max_bytes} octets.",
                        )
                    handle.write(chunk)
    except httpx.HTTPStatusError as exc:
        destination.unlink(missing_ok=True)
        raise IngestionError(
            "source_unavailable",
            f"La source a répondu {exc.response.status_code}.",
        ) from exc
    except httpx.HTTPError as exc:
        destination.unlink(missing_ok=True)
        raise IngestionError("source_unavailable", f"Source injoignable : {exc}") from exc

    return FetchedFile(destination, written, _sha256(destination), "url", last_modified)


def fetch_local(source: Path, destination: Path, max_bytes: int) -> FetchedFile:
    """Copie un fichier local dans le répertoire des fichiers bruts."""
    if not source.is_file():
        raise IngestionError("file_not_found", f"Fichier introuvable : {source}")

    size = source.stat().st_size
    if size > max_bytes:
        raise IngestionError(
            "file_too_large",
            f"Le fichier fait {size} octets, au-delà de la limite de {max_bytes} octets.",
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    mtime = datetime.fromtimestamp(source.stat().st_mtime, tz=UTC)
    return FetchedFile(destination, size, _sha256(destination), "local", mtime)


def read_table(path: Path, config: dict[str, Any]) -> pd.DataFrame:
    """Lit le CSV en texte brut.

    Tout est lu en `str` volontairement : laisser Pandas deviner les types
    masquerait précisément ce que le contrôle de type doit détecter, et
    ferait perdre le zéro initial des codes postaux.
    """
    csv_config = config.get("csv", {})
    try:
        frame = pd.read_csv(
            path,
            sep=csv_config.get("separator", ";"),
            encoding=csv_config.get("encoding", "utf-8-sig"),
            dtype=str,
            keep_default_na=False,
            na_values=[""],
            low_memory=False,
        )
    except UnicodeDecodeError as exc:
        raise IngestionError(
            "unreadable_file",
            f"Encodage illisible avec {csv_config.get('encoding', 'utf-8-sig')} : {exc}",
        ) from exc
    except pd.errors.EmptyDataError as exc:
        raise IngestionError("empty_file", "Le fichier ne contient aucune donnée.") from exc
    except pd.errors.ParserError as exc:
        raise IngestionError("malformed_csv", f"CSV illisible : {exc}") from exc

    if frame.empty:
        raise IngestionError(
            "empty_file",
            "Le fichier ne contient aucune ligne : il n'y a rien à contrôler.",
        )
    return frame
