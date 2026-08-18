import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from tests.modules.analyse.conftest import CachePortEnMémoire, StockageImageEnMémoire

from composition.worker import create_worker_app
from modules.analyse.application.executer_job_generation import ExecuterJobGeneration
from modules.analyse.domaine.analyse import Analyse, SourceAnalyse, StatutAnalyse
from modules.analyse.ports.cache import CachePort
from modules.analyse.ports.generateur_ia import GenerateurIAPort
from modules.analyse.ports.stockage_image import StockageImagePort
from modules.ia.adaptateurs.generateur_ia_factice import GenerateurIAFactice
from shared.config import get_settings


@pytest.fixture
def worker_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    # Même montage que `tests/modules/analyse/adaptateurs/test_analyse_api.py` :
    # les variables d'environnement ne servent qu'à satisfaire `Settings`
    # au démarrage, aucune connexion Postgres réelle n'est ouverte avant que
    # le faux `CachePort` ne remplace l'adaptateur Postgres câblé au lifespan.
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    _dsn_test = "postgresql+asyncpg://test:test@localhost:5432/test"  # pragma: allowlist secret
    monkeypatch.setenv("DATABASE_URL", _dsn_test)
    monkeypatch.setenv("JWT_SIGNING_KEY", "cle-de-test-suffisamment-longue-32c")
    get_settings.cache_clear()

    app = create_worker_app()
    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()


def test_worker_expose_un_health_check(worker_client: TestClient) -> None:
    # Cloud Run (comme docker-compose en dev) a besoin de savoir que le
    # processus `worker` est démarré, indépendamment de tout job reçu.
    # L'endpoint interne qui reçoit les tâches Cloud Tasks (F3,
    # POST /internal/jobs/analyses) est couvert par
    # tests/modules/analyse/adaptateurs/test_api_worker.py.
    reponse = worker_client.get("/health")

    assert reponse.status_code == 200
    assert reponse.json() == {"status": "ok"}


def test_worker_ne_monte_aucune_route_analyse_ou_auth(worker_client: TestClient) -> None:
    # `worker` (F2, backlog.md) ne câble ni le router `analyse` (créer/lire
    # une analyse reste une responsabilité `api`) ni le router `auth` :
    # seul `api` reçoit des requêtes navigateur (composition/worker.py).
    assert worker_client.post("/analyses", json={}).status_code == 404
    assert worker_client.post("/auth/connexion", json={}).status_code == 404


def test_worker_cable_generateur_ia_et_stockage_image_par_defaut(
    worker_client: TestClient,
) -> None:
    # Sans `LLM_API_KEY`/`GCS_BUCKET_IMAGES` configurées (comme en dev
    # local), `worker` retient les mêmes adaptateurs factices/filesystem
    # que `api` (composition/adapters.py, F2 — même règle de bascule, pas
    # de duplication, agents.md §1).
    registry = worker_client.app.state.registry  # type: ignore[union-attr]
    assert isinstance(registry.resolve(GenerateurIAPort), GenerateurIAFactice)
    assert registry.resolve(StockageImagePort) is not None


async def test_worker_traite_un_job_de_bout_en_bout(worker_client: TestClient) -> None:
    # Reproduit à la main ce que fait l'endpoint interne du worker (F3,
    # modules/analyse/adaptateurs/api_worker.py) une fois le jeton OIDC
    # vérifié : résoudre les ports depuis le registre câblé par
    # `create_worker_app`, construire `ExecuterJobGeneration` (F1 — la
    # génération IA extraite de `GenererAnalyse`) et l'exécuter sur un job
    # `pending`. C'est la preuve que la composition dédiée au worker (F2)
    # suffit à faire tourner un job de bout en bout, indépendamment du
    # transport HTTP/Cloud Tasks — que `test_api_worker.py` teste, lui, en
    # passant par le vrai endpoint.
    registry = worker_client.app.state.registry  # type: ignore[union-attr]
    cache = CachePortEnMémoire()
    registry.register(CachePort, cache)
    stockage_image = StockageImageEnMémoire()
    registry.register(StockageImagePort, stockage_image)

    analyse = Analyse(
        id=uuid.uuid4(),
        texte_source="mon profil github",
        source=SourceAnalyse.GITHUB,
        statut=StatutAnalyse.PENDING,
        created_at=datetime.now(UTC),
    )
    await cache.inserer_si_absent(analyse)

    job = ExecuterJobGeneration(
        cache=registry.resolve(CachePort),
        generateur_ia=registry.resolve(GenerateurIAPort),
        stockage_image=registry.resolve(StockageImagePort),
    )
    resultat = await job.executer(analyse)

    assert resultat.statut is StatutAnalyse.DONE
    assert resultat.resultat_texte
    assert resultat.resultat_image_url == f"memoire://{analyse.id}"
