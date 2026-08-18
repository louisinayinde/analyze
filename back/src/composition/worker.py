from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI

from composition.adapters import build_generateur_ia, build_stockage_image
from composition.error_handling import configure_error_handling
from composition.registry import Registry
from modules.analyse.index import router_interne as analyse_router_interne
from modules.analyse.ports.cache import CachePort
from modules.analyse.ports.generateur_ia import GenerateurIAPort
from modules.analyse.ports.stockage_image import StockageImagePort
from modules.cache.index import CacheResultatPostgres
from shared.config import Settings, get_settings
from shared.correlation import CorrelationIdMiddleware
from shared.db import create_engine, create_session_factory
from shared.logging import configure_logging


def create_worker_app() -> FastAPI:
    """Composition du processus `worker` (F2, backlog.md).

    Même monolithe modulaire que `composition/app.py` (`api`), point
    d'entrée différent (agents.md §4 — projets.md : « les deux partagent
    le même monolithe modulaire, juste un point d'entrée différent »).

    Ne câble que ce dont le worker a réellement besoin pour exécuter la
    génération IA d'un job : `CachePort`, `GenerateurIAPort` (décoré par
    son propre `CircuitBreaker`, indépendant de celui de `api` —
    `composition/adapters.py`), `StockageImagePort`. Contrairement à
    `create_app()` : pas de router `auth`, pas de router `analyse` (créer/
    lire une analyse reste une responsabilité `api`), pas de CORS (aucune
    requête navigateur n'atteint ce processus), pas de montage `/images`
    (seul `api` sert des fichiers au navigateur). `ExecuterJobGeneration`
    (F1, la génération IA proprement dite) est le seul use-case que ce
    processus exécute — construit à la demande par l'appelant du job
    (les tests d'intégration de F2, et depuis F3 par `router_interne`,
    monté ci-dessous : l'endpoint HTTP qui reçoit les tâches Cloud Tasks
    et appelle ce même registre).

    `configure_error_handling`/`CorrelationIdMiddleware` sont réutilisés
    tels quels (agents.md §1, DRY) : `worker` doit produire la même
    enveloppe d'erreur JSON et propager le même `correlation_id` que
    `api` (projets.md §Observabilité — corrélation front → api → worker),
    prêts pour l'endpoint que F3 ajoutera à cette même app plutôt que d'en
    créer une nouvelle.
    """
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(lifespan=_build_lifespan(settings))
    app.state.registry = Registry()
    app.state.settings = settings

    app.state.registry.register(GenerateurIAPort, build_generateur_ia(settings))
    app.state.registry.register(StockageImagePort, build_stockage_image(settings))

    app.add_middleware(CorrelationIdMiddleware)
    configure_error_handling(app)

    # `router_interne` (F3, backlog.md) : seule route métier de ce
    # processus, celle que Cloud Tasks appelle en prod. Jamais monté sur
    # `api` (composition/app.py) — symétrique de `router` (routes
    # `/analyses`), jamais monté ici (test_worker_ne_monte_aucune_route_
    # analyse_ou_auth).
    app.include_router(analyse_router_interne)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def _build_lifespan(
    settings: Settings,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Même motif que `composition/app.py._build_lifespan` : engine créé
        # au démarrage du processus, pas à l'import, pour que `worker` ouvre
        # son propre pool borné (shared/db.py), distinct de celui de `api`.
        engine = create_engine(settings)
        app.state.db_engine = engine
        app.state.db_sessionmaker = create_session_factory(engine)
        app.state.registry.register(CachePort, CacheResultatPostgres(app.state.db_sessionmaker))
        try:
            yield
        finally:
            await engine.dispose()

    return lifespan
