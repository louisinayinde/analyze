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
    # `create_app()` lit `Settings` depuis l'environnement (B2) : ces
    # valeurs ne servent qu'à satisfaire la validation Pydantic au
    # démarrage, aucune connexion Postgres réelle n'est ouverte (le pool
    # SQLAlchemy async se connecte à la demande, jamais à la création de
    # l'engine — voir `shared/db.py`). Le dépôt réel est de toute façon
    # remplacé juste après par le faux dépôt en mémoire, avant toute
    # requête.
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    # DSN factice, jamais utilisé pour une vraie connexion (voir commentaire ci-dessus).
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


def test_inscription_nominale_retourne_201_sans_le_hash(client: TestClient) -> None:
    reponse = client.post(
        "/auth/inscription",
        json={"email": "nouvel.user@example.com", "mot_de_passe": MOT_DE_PASSE_ROBUSTE},
    )

    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["email"] == "nouvel.user@example.com"
    assert "id" in corps
    # Le hash n'est jamais renvoyé au client (agents.md §7).
    assert "password_hash" not in corps
    assert "mot_de_passe" not in corps


def test_inscription_avec_email_deja_pris_retourne_409_generique(client: TestClient) -> None:
    client.post(
        "/auth/inscription",
        json={"email": "double@example.com", "mot_de_passe": MOT_DE_PASSE_ROBUSTE},
    )

    reponse = client.post(
        "/auth/inscription",
        json={"email": "double@example.com", "mot_de_passe": MOT_DE_PASSE_ROBUSTE},
    )

    assert reponse.status_code == 409
    corps = reponse.json()
    assert corps["code"] == "conflit_ressource"
    # Enveloppe standardisée (B4) : code stable + correlation_id, jamais de
    # détail interne (ex. confirmation explicite que l'email existe déjà).
    assert "correlation_id" in corps
    assert "existe déjà" not in corps["message"]


def test_connexion_nominale_retourne_des_jetons(client: TestClient) -> None:
    client.post(
        "/auth/inscription",
        json={"email": "nouvel.user@example.com", "mot_de_passe": MOT_DE_PASSE_ROBUSTE},
    )

    reponse = client.post(
        "/auth/connexion",
        json={"email": "nouvel.user@example.com", "mot_de_passe": MOT_DE_PASSE_ROBUSTE},
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["token_type"] == "bearer"
    assert corps["access_token"]
    assert corps["refresh_token"]
    assert corps["expires_in"] == 15 * 60


def test_connexion_avec_email_inconnu_retourne_401_generique(client: TestClient) -> None:
    reponse = client.post(
        "/auth/connexion",
        json={"email": "inconnu@example.com", "mot_de_passe": MOT_DE_PASSE_ROBUSTE},
    )

    assert reponse.status_code == 401
    corps = reponse.json()
    assert corps["code"] == "non_authentifie"
    assert corps["message"] == "Email ou mot de passe incorrect."


def test_connexion_avec_mot_de_passe_incorrect_retourne_le_meme_message_que_email_inconnu(
    client: TestClient,
) -> None:
    client.post(
        "/auth/inscription",
        json={"email": "nouvel.user@example.com", "mot_de_passe": MOT_DE_PASSE_ROBUSTE},
    )

    reponse = client.post(
        "/auth/connexion",
        json={"email": "nouvel.user@example.com", "mot_de_passe": "mauvais-mot-de-passe-9"},
    )

    assert reponse.status_code == 401
    # Pas d'oracle : le message est strictement identique à celui d'un
    # email inconnu (agents.md §7 — pas d'énumération d'utilisateurs).
    assert reponse.json()["message"] == "Email ou mot de passe incorrect."


def _connecter(client: TestClient) -> str:
    client.post(
        "/auth/inscription",
        json={"email": "nouvel.user@example.com", "mot_de_passe": MOT_DE_PASSE_ROBUSTE},
    )
    reponse = client.post(
        "/auth/connexion",
        json={"email": "nouvel.user@example.com", "mot_de_passe": MOT_DE_PASSE_ROBUSTE},
    )
    refresh_token: str = reponse.json()["refresh_token"]
    return refresh_token


def test_refresh_nominal_retourne_une_nouvelle_paire_de_jetons(client: TestClient) -> None:
    refresh_token = _connecter(client)

    reponse = client.post("/auth/refresh", json={"refresh_token": refresh_token})

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["refresh_token"] != refresh_token
    assert corps["access_token"]
    assert corps["token_type"] == "bearer"


def test_refresh_rejoue_retourne_401_et_invalide_meme_la_rotation_legitime(
    client: TestClient,
) -> None:
    # Coeur du ticket C6 : présenter deux fois le même refresh token révoque
    # toute la famille, pas seulement le jeton rejoué (agents.md §7).
    refresh_token = _connecter(client)

    premiere_rotation = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert premiere_rotation.status_code == 200
    nouveau_refresh_token = premiere_rotation.json()["refresh_token"]

    reponse_rejeu = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert reponse_rejeu.status_code == 401
    assert reponse_rejeu.json()["code"] == "refresh_rejoue"

    # Le refresh légitime, pourtant jamais présenté deux fois, est lui aussi
    # rejeté : toute la famille a été révoquée par le rejeu ci-dessus.
    reponse_apres_revocation = client.post(
        "/auth/refresh", json={"refresh_token": nouveau_refresh_token}
    )
    assert reponse_apres_revocation.status_code == 401


def test_refresh_avec_jeton_invalide_retourne_401_generique(client: TestClient) -> None:
    reponse = client.post("/auth/refresh", json={"refresh_token": "pas-un-jwt"})

    assert reponse.status_code == 401
    assert reponse.json()["code"] == "non_authentifie"


def test_refresh_avec_un_access_token_retourne_401(client: TestClient) -> None:
    client.post(
        "/auth/inscription",
        json={"email": "nouvel.user@example.com", "mot_de_passe": MOT_DE_PASSE_ROBUSTE},
    )
    connexion = client.post(
        "/auth/connexion",
        json={"email": "nouvel.user@example.com", "mot_de_passe": MOT_DE_PASSE_ROBUSTE},
    )
    access_token = connexion.json()["access_token"]

    reponse = client.post("/auth/refresh", json={"refresh_token": access_token})

    assert reponse.status_code == 401


def test_deconnexion_nominale_retourne_204(client: TestClient) -> None:
    refresh_token = _connecter(client)

    reponse = client.post("/auth/deconnexion", json={"refresh_token": refresh_token})

    assert reponse.status_code == 204


def test_deconnexion_revoque_le_refresh_qui_ne_peut_plus_etre_utilise_pour_rafraichir(
    client: TestClient,
) -> None:
    # Coeur du ticket C7 : après déconnexion, le refresh présenté n'est plus
    # utilisable pour obtenir une nouvelle paire de jetons.
    refresh_token = _connecter(client)

    client.post("/auth/deconnexion", json={"refresh_token": refresh_token})

    reponse = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert reponse.status_code == 401


def test_deconnexion_avec_un_refresh_deja_revoque_reste_204(client: TestClient) -> None:
    # Idempotence côté HTTP (agents.md §6) : appeler deux fois la
    # déconnexion avec le même jeton ne doit jamais faire échouer la
    # seconde requête.
    refresh_token = _connecter(client)
    client.post("/auth/deconnexion", json={"refresh_token": refresh_token})

    reponse = client.post("/auth/deconnexion", json={"refresh_token": refresh_token})

    assert reponse.status_code == 204


def test_deconnexion_avec_un_jeton_invalide_reste_204(client: TestClient) -> None:
    # Ni oracle ni erreur sur un jeton mal formé : le client obtient de
    # toute façon ce qu'il voulait (ne plus être authentifié).
    reponse = client.post("/auth/deconnexion", json={"refresh_token": "pas-un-jwt"})

    assert reponse.status_code == 204
