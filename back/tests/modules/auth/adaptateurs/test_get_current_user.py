import uuid
from collections.abc import Iterator

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from tests.modules.auth.conftest import DépôtRefreshTokenEnMémoire, DépôtUtilisateurEnMémoire

from composition.app import create_app
from modules.auth.index import get_current_user
from modules.auth.ports.depot_refresh_token import DépôtRefreshTokenPort
from modules.auth.ports.depot_utilisateur import DépôtUtilisateurPort
from shared.config import get_settings

MOT_DE_PASSE_ROBUSTE = "cheval-trombone-9"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    # Même montage que `test_api.py`, avec une route de test additionnelle
    # protégée par `get_current_user` : ce ticket (C7) n'introduit encore
    # aucune vraie route protégée (réservé aux modules D, H à venir), donc
    # il faut une route jetable pour exercer la dépendance de bout en bout,
    # exactement comme le ferait une future route réelle
    # (`Depends(get_current_user)`, importée depuis la surface publique du
    # module — jamais `adaptateurs.api` directement, agents.md §4).
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    # DSN factice, jamais utilisé pour une vraie connexion (voir `test_api.py`).
    _dsn_test = "postgresql+asyncpg://test:test@localhost:5432/test"  # pragma: allowlist secret
    monkeypatch.setenv("DATABASE_URL", _dsn_test)
    monkeypatch.setenv("JWT_SIGNING_KEY", "cle-de-test-suffisamment-longue-32c")
    get_settings.cache_clear()

    app = create_app()

    @app.get("/__test__/protegee")
    async def route_protegee(user_id: uuid.UUID = Depends(get_current_user)) -> dict[str, str]:
        return {"user_id": str(user_id)}

    with TestClient(app) as test_client:
        app.state.registry.register(DépôtUtilisateurPort, DépôtUtilisateurEnMémoire())
        app.state.registry.register(DépôtRefreshTokenPort, DépôtRefreshTokenEnMémoire())
        yield test_client

    get_settings.cache_clear()


def _connecter(client: TestClient) -> tuple[str, str]:
    client.post(
        "/auth/inscription",
        json={"email": "nouvel.user@example.com", "mot_de_passe": MOT_DE_PASSE_ROBUSTE},
    )
    reponse = client.post(
        "/auth/connexion",
        json={"email": "nouvel.user@example.com", "mot_de_passe": MOT_DE_PASSE_ROBUSTE},
    )
    corps = reponse.json()
    return corps["access_token"], corps["refresh_token"]


def test_route_protegee_avec_un_access_token_valide_retourne_200(client: TestClient) -> None:
    access_token, _ = _connecter(client)

    reponse = client.get("/__test__/protegee", headers={"Authorization": f"Bearer {access_token}"})

    assert reponse.status_code == 200
    # `user_id` bien extrait du jeton, pas une valeur factice.
    assert uuid.UUID(reponse.json()["user_id"])


def test_route_protegee_sans_en_tete_authorization_retourne_401(client: TestClient) -> None:
    reponse = client.get("/__test__/protegee")

    assert reponse.status_code == 401
    assert reponse.json()["code"] == "non_authentifie"


def test_route_protegee_avec_un_jeton_invalide_retourne_401(client: TestClient) -> None:
    reponse = client.get("/__test__/protegee", headers={"Authorization": "Bearer pas-un-jwt"})

    assert reponse.status_code == 401


def test_route_protegee_avec_un_refresh_token_retourne_401(client: TestClient) -> None:
    # Symétrique de `/auth/refresh` refusant un access token (C6) : ici,
    # c'est un refresh (longue durée) qui ne doit pas pouvoir se substituer
    # à un access token pour accéder à une route protégée.
    _, refresh_token = _connecter(client)

    reponse = client.get("/__test__/protegee", headers={"Authorization": f"Bearer {refresh_token}"})

    assert reponse.status_code == 401
