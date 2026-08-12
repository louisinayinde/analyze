from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from composition.registry import Registry
from shared.config import Settings, get_settings
from shared.correlation import CorrelationIdMiddleware
from shared.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI()
    app.state.registry = Registry()
    app.state.settings = settings

    _configure_cors(app, settings)
    # Ajouté après CORS pour l'englober (agents.md §3 : correlation_id
    # propagé de bout en bout, y compris pour les réponses touchées par
    # le middleware CORS). Voir shared/correlation.py.
    app.add_middleware(CorrelationIdMiddleware)

    for router in _routers():
        app.include_router(router)

    _mount_health(app)

    return app


def _configure_cors(app: FastAPI, settings: Settings) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_methods=["GET"],
    )


def _routers() -> tuple[APIRouter, ...]:
    # Chaque module expose son router via son `index.py` (agents.md §4).
    # Vide tant qu'aucun module n'en a un (arrive en C5, D4, D5...).
    return ()


def _mount_health(app: FastAPI) -> None:
    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}
