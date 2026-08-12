import os

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from composition.registry import Registry


def create_app() -> FastAPI:
    app = FastAPI()
    app.state.registry = Registry()

    _configure_cors(app)

    for router in _routers():
        app.include_router(router)

    _mount_health(app)

    return app


def _configure_cors(app: FastAPI) -> None:
    origins = [
        origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
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
