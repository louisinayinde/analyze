from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from composition.registry import Registry
from shared.config import Settings, get_settings
from shared.correlation import CORRELATION_ID_HEADER, CorrelationIdMiddleware, get_correlation_id
from shared.db import create_engine, create_session_factory
from shared.errors import ErreurAPI, ErreurDomaine
from shared.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(lifespan=_build_lifespan(settings))
    app.state.registry = Registry()
    app.state.settings = settings

    _configure_cors(app, settings)
    # Ajouté après CORS pour l'englober (agents.md §3 : correlation_id
    # propagé de bout en bout, y compris pour les réponses touchées par
    # le middleware CORS). Voir shared/correlation.py.
    app.add_middleware(CorrelationIdMiddleware)
    _configure_error_handling(app)

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


def _configure_error_handling(app: FastAPI) -> None:
    """Centralise le mapping exception → réponse HTTP (agents.md §4, §9).

    Un seul endroit connaît la correspondance entre une exception et son
    code HTTP : une route lève une `ErreurDomaine` (ou laisse une exception
    FastAPI standard remonter) et n'a jamais à formatter sa propre réponse
    d'erreur ni à dupliquer un try/except (agents.md §6).
    """

    @app.exception_handler(ErreurDomaine)
    async def _erreur_domaine(request: Request, exc: ErreurDomaine) -> JSONResponse:
        return _reponse_erreur(request, exc.status_code, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _erreur_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _reponse_erreur(request, exc.status_code, "erreur_http", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _erreur_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _reponse_erreur(
            request,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "entree_invalide",
            "La requête ne respecte pas le format attendu.",
        )

    @app.exception_handler(Exception)
    async def _erreur_inattendue(request: Request, exc: Exception) -> JSONResponse:
        # Remplace le comportement par défaut de Starlette (page 500 non
        # formattée) par la même enveloppe JSON que le reste des erreurs.
        # Pas de log ici : CorrelationIdMiddleware (shared/correlation.py)
        # journalise déjà la trace complète avant que cette exception ne
        # remonte jusqu'ici — un second appel ferait un doublon (agents.md §2).
        return _reponse_erreur(
            request,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "erreur_interne",
            "Une erreur inattendue est survenue.",
        )


def _reponse_erreur(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
    # `request.state.correlation_id` (posé par CorrelationIdMiddleware avant
    # tout traitement) est la source fiable : contrairement au contextvar,
    # il survit même quand ce handler s'exécute après coup, au niveau du
    # middleware le plus externe (cas du handler `Exception` ci-dessus).
    correlation_id = getattr(request.state, "correlation_id", None) or get_correlation_id()
    erreur = ErreurAPI(code=code, message=message, correlation_id=correlation_id)
    response = JSONResponse(status_code=status_code, content=erreur.model_dump())
    response.headers[CORRELATION_ID_HEADER] = correlation_id
    return response


def _build_lifespan(
    settings: Settings,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Engine créé au démarrage (pas à l'import du module) pour que
        # chaque processus (api, futur worker) ouvre son propre pool borné
        # (shared/db.py) plutôt que d'en partager un global implicite.
        engine = create_engine(settings)
        app.state.db_engine = engine
        app.state.db_sessionmaker = create_session_factory(engine)
        try:
            yield
        finally:
            # Ferme proprement toutes les connexions du pool à l'arrêt
            # (reload, redeploy) : sans ça, chaque redémarrage fuit des
            # connexions côté Postgres jusqu'à épuisement (agents.md §9).
            await engine.dispose()

    return lifespan


def _routers() -> tuple[APIRouter, ...]:
    # Chaque module expose son router via son `index.py` (agents.md §4).
    # Vide tant qu'aucun module n'en a un (arrive en C5, D4, D5...).
    return ()


def _mount_health(app: FastAPI) -> None:
    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}
