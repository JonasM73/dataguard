"""Point d'entrée de l'API DataGuard."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.api.errors import register_error_handlers
from app.api.routes import datasets, health, runs, sources
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.telemetry import configure_tracing

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.env != "local")
    configure_tracing(settings.otel_exporter, service_name="dataguard-api")
    get_logger(__name__).info("api.startup", env=settings.env)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="DataGuard",
        version="0.1.0",
        summary="Qualité et observabilité des données publiques",
        description=(
            "Ingère une source publique, exécute des contrôles de qualité, calcule un "
            "score expliqué et compare chaque exécution à la précédente.\n\n"
            "Le score est une aide à la lecture : il n'est jamais publié sans le détail "
            "des contrôles qui le composent, et les poids employés sont recopiés dans "
            "chaque résultat."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    for module in (health, sources, datasets, runs):
        app.include_router(module.router, prefix=API_PREFIX)

    FastAPIInstrumentor.instrument_app(app)
    return app


app = create_app()
