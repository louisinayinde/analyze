from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from composition.registry import Registry
from modules.analyse.domaine.analyse import Analyse
from modules.analyse.index import (
    ExecuterJobGeneration,
    FileJobsCloudTasks,
    FileJobsEnProcessusImmediat,
    StockageImageFilesystem,
    StockageImageGCS,
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
from modules.ia.index import AdaptateurClaude, GenerateurIAAvecCircuitBreaker, GenerateurIAFactice
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
    # `GenerateurIAPort` -> `AdaptateurClaude` (E1/E2, texte + image) si une
    # clé API est configurée, sinon `GenerateurIAFactice` (D1) : évite de
    # forcer une clé Anthropic payante juste pour lancer l'API en dev local
    # (agents.md §2, budget — même esprit que « on ne paie pas d'infra pour
    # itérer sur de la logique validable gratuitement »). Câblés ici pour la
    # même raison que `HacheurArgon2id`/`EmetteurJWT` ci-dessus : aucun de
    # ces adaptateurs n'a d'I/O à initialiser à la construction. Remplacer
    # `GenerateurIAFactice` par `AdaptateurClaude` ne touche aucune ligne du
    # use-case `GenererAnalyse` (D3, agents.md §4).
    #
    # `AdaptateurClaude` est décoré par `GenerateurIAAvecCircuitBreaker`
    # (E4, backlog.md) : seul le chemin réel passe par le disjoncteur —
    # `GenerateurIAFactice` ne fait aucun appel réseau, rien à isoler.
    if settings.llm_api_key:
        app.state.registry.register(
            GenerateurIAPort,
            GenerateurIAAvecCircuitBreaker(
                AdaptateurClaude(api_key=settings.llm_api_key, modele=settings.llm_model)
            ),
        )
    else:
        app.state.registry.register(GenerateurIAPort, GenerateurIAFactice())

    # `StockageImagePort` (E5, backlog.md) -> `StockageImageGCS` si un
    # bucket est configuré, sinon `StockageImageFilesystem` : même bascule
    # que `GenerateurIAPort` ci-dessus, sur le même principe (agents.md §2 —
    # `GCS_BUCKET_IMAGES` ne sera renseignée en prod qu'une fois L4
    # (provisionnement Terraform du bucket) fait). Remplacer l'un par
    # l'autre ne touche aucune ligne du use-case `GenererAnalyse` (D3,
    # agents.md §4).
    if settings.gcs_bucket_images:
        app.state.registry.register(
            StockageImagePort, StockageImageGCS(bucket=settings.gcs_bucket_images)
        )
    else:
        repertoire_images = Path(settings.local_storage_dir)
        app.state.registry.register(
            StockageImagePort,
            StockageImageFilesystem(
                repertoire=repertoire_images, url_publique_base=settings.api_public_url
            ),
        )
        # Sert les fichiers écrits par `StockageImageFilesystem` en HTTP :
        # sans ce montage, l'URL renvoyée par l'adaptateur (`/images/...`)
        # ne répondrait rien. Absent en prod (branche GCS ci-dessus) — les
        # images y sont servies directement par GCS/Cloud CDN (L4), jamais
        # par ce processus API. `check_dir=False` : le dossier n'est créé
        # qu'au premier `stocker()` (adaptateur, agents.md §2 YAGNI) —
        # sans ça, `StaticFiles` lève au montage si aucune image n'a encore
        # été générée (ex. premier boot, ou tests qui construisent l'app
        # sans jamais déclencher d'écriture réelle).
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
    _configure_error_handling(app)

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
