import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from google.auth import exceptions as google_auth_exceptions
from tests.modules.analyse.conftest import CachePortEnMémoire, StockageImageEnMémoire

from composition.worker import create_worker_app
from modules.analyse.adaptateurs import api_worker
from modules.analyse.ports.cache import CachePort
from modules.analyse.ports.stockage_image import StockageImagePort
from shared.config import get_settings

_URL_WORKER = "https://worker.example.com/internal/jobs/analyses"
_SERVICE_ACCOUNT = "worker@projet-test.iam.gserviceaccount.com"


@pytest.fixture
def cache() -> CachePortEnMémoire:
    return CachePortEnMémoire()


@pytest.fixture
def worker_client(
    monkeypatch: pytest.MonkeyPatch, cache: CachePortEnMémoire
) -> Iterator[TestClient]:
    # Même montage que `tests/composition/test_worker.py` : les variables
    # d'environnement satisfont `Settings` au démarrage, aucune connexion
    # Postgres réelle n'est ouverte avant que le faux `CachePort` ne
    # remplace l'adaptateur Postgres câblé au lifespan. `WORKER_INTERNAL_URL`/
    # `WORKER_SERVICE_ACCOUNT_EMAIL` sont les deux valeurs que
    # `verifier_origine_cloud_tasks` compare au jeton OIDC reçu.
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    _dsn_test = "postgresql+asyncpg://test:test@localhost:5432/test"  # pragma: allowlist secret
    monkeypatch.setenv("DATABASE_URL", _dsn_test)
    monkeypatch.setenv("JWT_SIGNING_KEY", "cle-de-test-suffisamment-longue-32c")
    monkeypatch.setenv("WORKER_INTERNAL_URL", _URL_WORKER)
    monkeypatch.setenv("WORKER_SERVICE_ACCOUNT_EMAIL", _SERVICE_ACCOUNT)
    get_settings.cache_clear()

    app = create_worker_app()
    with TestClient(app) as test_client:
        app.state.registry.register(CachePort, cache)
        app.state.registry.register(StockageImagePort, StockageImageEnMémoire())
        yield test_client

    get_settings.cache_clear()


def _corps_tache(analyse_id: uuid.UUID | None = None) -> dict[str, Any]:
    return {
        "analyse_id": str(analyse_id or uuid.uuid4()),
        "texte_source": "mon profil github",
        "source": "github",
    }


def _claims_valides() -> dict[str, Any]:
    return {"email": _SERVICE_ACCOUNT, "email_verified": True, "aud": _URL_WORKER}


def test_sans_jeton_oidc_retourne_403(worker_client: TestClient) -> None:
    # Coeur du ticket F3 : sans jeton, l'endpoint interne n'est pas
    # appelable, même par un appelant qui connaît juste l'URL (agents.md §7).
    reponse = worker_client.post("/internal/jobs/analyses", json=_corps_tache())

    assert reponse.status_code == 403
    assert reponse.json()["code"] == "acces_refuse"


def test_jeton_oidc_invalide_retourne_403(
    worker_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _verify_en_echec(*args: object, **kwargs: object) -> dict[str, Any]:
        raise google_auth_exceptions.InvalidValue("signature invalide")

    monkeypatch.setattr(api_worker.id_token, "verify_oauth2_token", _verify_en_echec)

    reponse = worker_client.post(
        "/internal/jobs/analyses",
        json=_corps_tache(),
        headers={"Authorization": "Bearer pas-un-jeton-oidc-valide"},
    )

    assert reponse.status_code == 403
    assert reponse.json()["code"] == "acces_refuse"


def test_jeton_oidc_signe_par_un_autre_compte_de_service_retourne_403(
    worker_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Un jeton Google par ailleurs valide, mais signé par un compte de
    # service différent de celui attendu, ne doit pas suffire — sans ce
    # contrôle, n'importe quel service GCP capable d'obtenir un jeton OIDC
    # Google pourrait appeler cet endpoint (docstring de
    # `verifier_origine_cloud_tasks`).
    def _verify_autre_compte(*args: object, **kwargs: object) -> dict[str, Any]:
        return {
            "email": "un-autre-service@autre-projet.iam.gserviceaccount.com",
            "email_verified": True,
            "aud": _URL_WORKER,
        }

    monkeypatch.setattr(api_worker.id_token, "verify_oauth2_token", _verify_autre_compte)

    reponse = worker_client.post(
        "/internal/jobs/analyses",
        json=_corps_tache(),
        headers={"Authorization": "Bearer jeton-google-valide-mauvais-compte"},
    )

    assert reponse.status_code == 403
    assert reponse.json()["code"] == "acces_refuse"


def test_jeton_oidc_valide_verifie_l_audience_attendue(
    worker_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    appels: list[dict[str, Any]] = []

    def _verify_espion(token: str, request: object, audience: str) -> dict[str, Any]:
        appels.append({"token": token, "audience": audience})
        return _claims_valides()

    monkeypatch.setattr(api_worker.id_token, "verify_oauth2_token", _verify_espion)

    reponse = worker_client.post(
        "/internal/jobs/analyses",
        json=_corps_tache(),
        headers={"Authorization": "Bearer jeton-google-valide"},
    )

    assert reponse.status_code == 204
    assert len(appels) == 1
    assert appels[0]["token"] == "jeton-google-valide"
    # `worker_internal_url` (settings) est l'audience attendue du jeton :
    # même valeur que celle utilisée par `FileJobsCloudTasks` pour signer la
    # tâche (`tasks_v2.OidcToken.audience`, F1).
    assert appels[0]["audience"] == _URL_WORKER


async def test_jeton_oidc_valide_execute_le_job_et_marque_l_analyse_done(
    worker_client: TestClient, monkeypatch: pytest.MonkeyPatch, cache: CachePortEnMémoire
) -> None:
    monkeypatch.setattr(
        api_worker.id_token, "verify_oauth2_token", lambda *a, **k: _claims_valides()
    )
    analyse_id = uuid.uuid4()

    reponse = worker_client.post(
        "/internal/jobs/analyses",
        json=_corps_tache(analyse_id),
        headers={"Authorization": "Bearer jeton-google-valide"},
    )

    assert reponse.status_code == 204
    assert reponse.content == b""
    relue = await cache.obtenir_par_id(analyse_id)
    assert relue is not None
    assert relue.statut.value == "done"
    assert relue.resultat_texte


def test_corps_de_requete_invalide_retourne_422(
    worker_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        api_worker.id_token, "verify_oauth2_token", lambda *a, **k: _claims_valides()
    )

    reponse = worker_client.post(
        "/internal/jobs/analyses",
        json={"analyse_id": "pas-un-uuid", "texte_source": "x", "source": "github"},
        headers={"Authorization": "Bearer jeton-google-valide"},
    )

    assert reponse.status_code == 422
    assert reponse.json()["code"] == "entree_invalide"


def test_worker_ne_monte_pas_l_endpoint_interne_sur_l_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Symétrique de `test_worker_ne_monte_aucune_route_analyse_ou_auth`
    # (tests/composition/test_worker.py) : l'endpoint interne du worker
    # (F3) est réservé au processus `worker`, jamais exposé par `api`
    # (composition/app.py) — seul `worker` doit recevoir des tâches Cloud
    # Tasks.
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    _dsn_test = "postgresql+asyncpg://test:test@localhost:5432/test"  # pragma: allowlist secret
    monkeypatch.setenv("DATABASE_URL", _dsn_test)
    monkeypatch.setenv("JWT_SIGNING_KEY", "cle-de-test-suffisamment-longue-32c")
    get_settings.cache_clear()

    from composition.app import create_app

    app = create_app()
    with TestClient(app) as test_client:
        reponse = test_client.post("/internal/jobs/analyses", json=_corps_tache())

    get_settings.cache_clear()
    assert reponse.status_code == 404
