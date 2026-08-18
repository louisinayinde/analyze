from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from tests.modules.auth.conftest import DépôtRefreshTokenEnMémoire, DépôtUtilisateurEnMémoire

from composition.app import create_app
from modules.auth.ports.depot_refresh_token import DépôtRefreshTokenPort
from modules.auth.ports.depot_utilisateur import DépôtUtilisateurPort
from shared.config import get_settings

MOT_DE_PASSE_ROBUSTE = "cheval-trombone-9"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    # Même montage que tests/modules/auth/adaptateurs/test_api.py.
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    _dsn_test = "postgresql+asyncpg://test:test@localhost:5432/test"  # pragma: allowlist secret
    monkeypatch.setenv("DATABASE_URL", _dsn_test)
    monkeypatch.setenv("JWT_SIGNING_KEY", "cle-de-test-suffisamment-longue-32c")
    get_settings.cache_clear()

    app = create_app()
    with TestClient(app) as test_client:
        app.state.registry.register(DépôtUtilisateurPort, DépôtUtilisateurEnMémoire())
        app.state.registry.register(DépôtRefreshTokenPort, DépôtRefreshTokenEnMémoire())
        yield test_client

    get_settings.cache_clear()


def _access_token(client: TestClient, email: str) -> str:
    client.post("/auth/inscription", json={"email": email, "mot_de_passe": MOT_DE_PASSE_ROBUSTE})
    reponse = client.post(
        "/auth/connexion", json={"email": email, "mot_de_passe": MOT_DE_PASSE_ROBUSTE}
    )
    access_token: str = reponse.json()["access_token"]
    return access_token


def test_suppression_sans_authentification_retourne_401(client: TestClient) -> None:
    reponse = client.request("DELETE", "/compte", json={"mot_de_passe": MOT_DE_PASSE_ROBUSTE})

    assert reponse.status_code == 401
    assert reponse.json()["code"] == "non_authentifie"


def test_suppression_avec_mauvais_mot_de_passe_retourne_401_et_conserve_le_compte(
    client: TestClient,
) -> None:
    access_token = _access_token(client, "conserve@example.com")

    reponse = client.request(
        "DELETE",
        "/compte",
        json={"mot_de_passe": "mauvais-mot-de-passe-9"},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert reponse.status_code == 401
    assert reponse.json()["code"] == "non_authentifie"
    # Le compte doit toujours pouvoir se connecter : la vérification
    # renforcée (agents.md §7) a bloqué la suppression avant tout effet.
    reponse_connexion = client.post(
        "/auth/connexion",
        json={"email": "conserve@example.com", "mot_de_passe": MOT_DE_PASSE_ROBUSTE},
    )
    assert reponse_connexion.status_code == 200


def test_suppression_nominale_retourne_204_et_le_compte_ne_peut_plus_se_connecter(
    client: TestClient,
) -> None:
    access_token = _access_token(client, "a.supprimer@example.com")

    reponse = client.request(
        "DELETE",
        "/compte",
        json={"mot_de_passe": MOT_DE_PASSE_ROBUSTE},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert reponse.status_code == 204
    reponse_connexion = client.post(
        "/auth/connexion",
        json={"email": "a.supprimer@example.com", "mot_de_passe": MOT_DE_PASSE_ROBUSTE},
    )
    assert reponse_connexion.status_code == 401


def test_suppression_avec_jeton_invalide_retourne_401(client: TestClient) -> None:
    reponse = client.request(
        "DELETE",
        "/compte",
        json={"mot_de_passe": MOT_DE_PASSE_ROBUSTE},
        headers={"Authorization": "Bearer pas-un-jwt"},
    )

    assert reponse.status_code == 401
