"""Interface en ligne de commande.

Elle appelle exactement le même pipeline que l'API : une exécution lancée au
terminal et une exécution lancée depuis le dashboard produisent le même run,
ce qui évite d'avoir deux chemins de code à maintenir et à tester.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import typer
from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.telemetry import configure_tracing
from app.db.models import Dataset, Source
from app.db.session import session_scope
from app.pipeline import run_pipeline

app = typer.Typer(help="DataGuard — qualité des données publiques", no_args_is_help=True)
logger = get_logger(__name__)


def sample_path(name: str) -> Path:
    """Localise un fichier de `data/sample`, quel que soit l'endroit d'où on lance.

    La CLI se lance depuis `backend/` en développement et depuis `/app` dans le
    conteneur, où le dossier est monté à un niveau différent. Coder un seul
    chemin relatif marcherait dans un cas et échouerait dans l'autre, sans que
    le message d'erreur n'indique lequel.
    """
    candidates = [Path("data/sample") / name, Path("../data/sample") / name]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def _bootstrap(trace: bool = False) -> None:
    """Prépare journalisation et traces.

    Les traces sont muettes par défaut ici : l'export console de
    OpenTelemetry déverse un objet JSON par span sur la sortie standard, ce qui
    noie complètement le résultat que la commande est censée montrer. Dans
    l'API elles partent dans le journal du serveur, où elles sont à leur place ;
    au terminal, on les demande explicitement avec --trace.
    """
    settings = get_settings()
    configure_logging(settings.log_level, json_output=False)
    configure_tracing(settings.otel_exporter if trace else "none", service_name="dataguard-cli")


@app.command("datasets")
def list_datasets() -> None:
    """Liste les datasets suivis."""
    _bootstrap()
    with session_scope() as session:
        for dataset in session.execute(select(Dataset).order_by(Dataset.created_at)).scalars():
            state = "actif" if dataset.active else "inactif"
            typer.echo(f"{dataset.id}  {dataset.name}  [{state}]")


@app.command("seed")
def seed(
    config_file: Path | None = typer.Option(
        None,
        "--config",
        help="Configuration du dataset ; par défaut data/sample/dataset_config.json",
    ),
    schema_file: Path | None = typer.Option(
        None,
        "--schema",
        help="Schéma de référence ; par défaut data/sample/reference_schema.json",
    ),
    name: str = typer.Option("Prix des carburants – flux instantané", "--name"),
    url: str = typer.Option(
        "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
        "prix-des-carburants-en-france-flux-instantane-v2/exports/csv"
        "?delimiter=%3B&use_labels=true",
        "--url",
    ),
    licence: str = typer.Option("Licence Ouverte / Open Licence 2.0", "--license"),
    frequency: str = typer.Option("P1D", "--frequency"),
) -> None:
    """Crée la source et le dataset de démonstration.

    Idempotent : relancer la commande ne crée pas de doublon, elle réutilise
    le dataset portant déjà ce nom.
    """
    _bootstrap()
    config_file = config_file or sample_path("dataset_config.json")
    schema_file = schema_file or sample_path("reference_schema.json")
    for path in (config_file, schema_file):
        if not path.is_file():
            typer.secho(
                f"Fichier introuvable : {path}\n"
                "Lancez la commande depuis la racine du dépôt ou depuis backend/, "
                "ou indiquez le chemin avec --config et --schema.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
    config = json.loads(config_file.read_text(encoding="utf-8"))
    reference = json.loads(schema_file.read_text(encoding="utf-8"))

    with session_scope() as session:
        existing = session.execute(select(Dataset).where(Dataset.name == name)).scalar_one_or_none()
        if existing is not None:
            typer.echo(f"dataset déjà présent : {existing.id}")
            return

        source = Source(name="data.economie.gouv.fr", url=url, format="csv", license=licence)
        session.add(source)
        session.flush()
        dataset = Dataset(
            source_id=source.id,
            name=name,
            description="Prix relevés dans les stations-service françaises.",
            expected_frequency=frequency,
            config=config,
            reference_schema={
                "fields": [
                    {k: f[k] for k in ("column_name", "data_type", "nullable", "position")}
                    for f in reference["fields"]
                ]
            },
        )
        session.add(dataset)
        session.flush()
        typer.echo(f"source  {source.id}")
        typer.echo(f"dataset {dataset.id}")


@app.command("run")
def run(
    dataset_id: str = typer.Argument(..., help="Identifiant du dataset"),
    file: Path | None = typer.Option(None, "--file", help="Fichier CSV local à ingérer"),
    json_output: bool = typer.Option(False, "--json", help="Affiche le rapport complet"),
    trace: bool = typer.Option(
        False, "--trace", help="Affiche les traces OpenTelemetry sur la sortie standard"
    ),
) -> None:
    """Lance une exécution sur un dataset."""
    _bootstrap(trace=trace)
    with session_scope() as session:
        dataset = session.get(Dataset, uuid.UUID(dataset_id))
        if dataset is None:
            typer.secho(f"Dataset {dataset_id} introuvable.", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        result = run_pipeline(session, dataset, local_file=file)
        session.flush()

        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "run_id": str(result.id),
                        "status": result.status,
                        "score": float(result.score) if result.score is not None else None,
                        "rows": result.rows_read,
                        "results": [
                            {
                                "check": r.check_name,
                                "status": r.status,
                                "failed_count": r.failed_count,
                            }
                            for r in result.results
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            typer.echo(f"run {result.id}  statut={result.status}  score={result.score}")
            if result.error_message:
                typer.secho(result.error_message, fg=typer.colors.RED)
            for r in sorted(result.results, key=lambda x: x.check_name):
                colour = {
                    "success": typer.colors.GREEN,
                    "warning": typer.colors.YELLOW,
                    "failed": typer.colors.RED,
                }.get(r.status, typer.colors.WHITE)
                typer.secho(f"  {r.check_name:14} {r.status:8} ({r.failed_count})", fg=colour)

        if result.status == "failed":
            raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
