from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from composition.adapters import build_generateur_ia, build_stockage_image
from composition.error_handling import configure_error_handling
from composition.registry import Registry
from modules.analyse.domaine.analyse import Analyse
from modules.analyse.index import (
    ExecuterJobGeneration,
    FileJobsCloudTasks,
    FileJobsEnProcessusImmediat,
)
from modules.analyse.index import router as analyse_router
from modules.analyse.ports.cache import CachePort
from modules.analyse.ports.file_jobs import FileJobsPort
from modules.analyse.ports.generateur_ia import GenerateurIAPort
from modules.analyse.ports.stockage_image import StockageImagePort
from modules.auth.adaptateurs.depot_refresh_token_postgres import DépôtRefreshTokenPostgres
from modules.auth.adaptateurs.depot_utilisateur_postgres import DépôtUtilisateurPostgres
from modules.auth.adaptateurs.emetteur_jwt import EmetteurJWT
from modules.auth.adaptateurs.hacheur_argon2id import HacheurArgon2id
from modules.auth.index import router as auth_router
from modules.auth.ports.depot_refresh_token import DépôtRefreshTokenPort
from modules.auth.ports.depot_utilisateur import DépôtUtilisateurPort
from modules.auth.ports.emetteur_jeton import EmetteurJetonPort
from modules.auth.ports.hacheur_mot_de_passe import HacheurMotDePassePort
from modules.cache.index import CacheResultatPostgres
from shared.config import Settings, get_settings
from shared.correlation import CorrelationIdMiddleware
from shared.db import create_engine, create_session_factory
from shared.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(lifespan=_build_lifespan(settings))
    app.state.registry = Registry()
    app.state.settings = settings

    # Câblage port -> adaptateur fait ici (et non dans le lifespan) : sans
    # I/O ni ressource async à initialiser, `HacheurArgon2id` et
    # `EmetteurJWT` peuvent être instanciés au moment de la construction de
    # l'app (agents.md §4).
    app.state.registry.register(HacheurMotDePassePort, HacheurArgon2id())
    app.state.registry.register(
        EmetteurJetonPort,
        EmetteurJWT(
            cle_signature=settings.jwt_signing_key,
            duree_access=timedelta(minutes=settings.jwt_access_token_expire_minutes),
            duree_refresh=timedelta(days=settings.jwt_refresh_token_expire_days),
        ),
    )
    # `GenerateurIAPort`/`StockageImagePort` : bascule dev/prod centralisée
    # dans `composition/adapters.py` (F2, backlog.md) pour que
    # `composition/worker.py` retienne exactement la même règle sans la
    # dupliquer (agents.md §1, DRY). Câblés ici (et non dans le lifespan) :
    # aucun des deux n'a d'I/O à initialiser à la construction. Remplacer
    # un adaptateur par un autre ne touche aucune ligne du use-case
    # `GenererAnalyse` (D3, agents.md §4).
    app.state.registry.register(GenerateurIAPort, build_generateur_ia(settings))

    app.state.registry.register(StockageImagePort, build_stockage_image(settings))
    if not settings.gcs_bucket_images:
        # Sert les fichiers écrits par `StockageImageFilesystem` (branche
        # dev de `build_stockage_image`) en HTTP : sans ce montage, l'URL
        # renvoyée par l'adaptateur (`/images/...`) ne répondrait rien.
        # Absent en prod (bucket GCS configuré) — les images y sont servies
        # directement par GCS/Cloud CDN (L4), jamais par ce processus API.
        # Concerne uniquement `api` : `worker` (composition/worker.py, F2)
        # écrit sur le même volume mais ne sert aucune requête navigateur,
        # donc ne monte jamais cette route. `check_dir=False` : le dossier
        # n'est créé qu'au premier `stocker()` (adaptateur, agents.md §2
        # YAGNI) — sans ça, `StaticFiles` lève au montage si aucune image
        # n'a encore été générée (ex. premier boot, ou tests qui
        # construisent l'app sans jamais déclencher d'écriture réelle).
        repertoire_images = Path(settings.local_storage_dir)
        app.mount(
            "/images", StaticFiles(directory=repertoire_images, check_dir=False), name="images"
        )

    # `FileJobsPort` (F1, backlog.md) -> `FileJobsCloudTasks` si une queue
    # est configurée, sinon `FileJobsEnProcessusImmediat` : même bascule
    # que `GenerateurIAPort`/`StockageImagePort` ci-dessus (agents.md §2 —
    # `CLOUD_TASKS_QUEUE` ne sera renseignée en prod qu'une fois L7 fait).
    # Câblé ici (et non dans le lifespan) : ni l'un ni l'autre adaptateur
    # n'a besoin du sessionmaker DB à la construction — `_executer_job`
    # résout `CachePort`/`GenerateurIAPort`/`StockageImagePort` depuis le
    # registre à l'exécution, pas à la construction, ce qui les rend
    # compatibles avec les tests qui remplacent ces adaptateurs par des
    # doubles en mémoire après `create_app()` (voir docstring de
    # `FileJobsEnProcessusImmediat`).
    async def _executer_job(analyse: Analyse) -> Analyse:
        executer_job_generation = ExecuterJobGeneration(
            cache=app.state.registry.resolve(CachePort),
            generateur_ia=app.state.registry.resolve(GenerateurIAPort),
            stockage_image=app.state.registry.resolve(StockageImagePort),
        )
        return await executer_job_generation.executer(analyse)

    if settings.cloud_tasks_queue:
        app.state.registry.register(
            FileJobsPort,
            FileJobsCloudTasks(
                project=settings.gcp_project_id,
                location=settings.gcp_region,
                queue=settings.cloud_tasks_queue,
                url_worker=settings.worker_internal_url,
                service_account_email=settings.worker_service_account_email,
            ),
        )
    else:
        app.state.registry.register(FileJobsPort, FileJobsEnProcessusImmediat(_executer_job))

    _configure_cors(app, settings)
    # Ajouté après CORS pour l'englober (agents.md §3 : correlation_id
    # propagé de bout en bout, y compris pour les réponses touchées par
    # le middleware CORS). Voir shared/correlation.py.
    app.add_middleware(CorrelationIdMiddleware)
    configure_error_handling(app)

    for router in _routers():
        app.include_router(router)

    _mount_health(app)

    return app


def _configure_cors(app: FastAPI, settings: Settings) -> None:
    # `allow_methods`/`allow_headers` grand ouverts : ce ne sont pas des
    # frontières de sécurité (le client n'est jamais l'autorité, agents.md
    # §7 — l'autorisation réelle se fait côté serveur, par endpoint). La
    # seule frontière que CORS doit tenir ici est `allow_origins`, restreint
    # à une allowlist exacte (`cors_origins_list`, jamais de wildcard).
    # `allow_credentials=True` : requis par le refresh token en cookie
    # httpOnly cross-origin (projets.md, Frontend) — incompatible avec un
    # `allow_origins=["*"]`, ce qui est cohérent puisqu'on n'en utilise pas.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )


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
        # Câblage port -> adaptateur, fait une seule fois ici (agents.md §4) :
        # les use-cases Auth (C3, C4) résolvent `DépôtUtilisateurPort` via
        # le registre sans jamais importer l'adaptateur Postgres. Fait dans
        # le lifespan (et non plus haut avec `HacheurArgon2id`/`EmetteurJWT`)
        # car cet adaptateur dépend du sessionmaker, lui-même issu de
        # l'engine créé ici — une vraie ressource I/O à initialiser.
        app.state.registry.register(
            DépôtUtilisateurPort, DépôtUtilisateurPostgres(app.state.db_sessionmaker)
        )
        app.state.registry.register(
            DépôtRefreshTokenPort, DépôtRefreshTokenPostgres(app.state.db_sessionmaker)
        )
        # `CachePort` (D1) -> adaptateur Postgres (D2) : câblé ici pour la
        # même raison que les dépôts Auth ci-dessus, dépend du même
        # sessionmaker. Le use-case `GenererAnalyse` (D3) le résout via le
        # registre sans jamais importer `CacheResultatPostgres`.
        app.state.registry.register(CachePort, CacheResultatPostgres(app.state.db_sessionmaker))
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
    # Complété au fil des modules (C5 pour auth ; D4 puis D5 pour analyse,
    # les deux routes de ce dernier partageant le même `APIRouter`).
    return (auth_router, analyse_router)


def _mount_health(app: FastAPI) -> None:
    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}
