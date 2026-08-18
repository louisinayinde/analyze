from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from tests.modules.analyse.conftest import (
    CachePortEnMémoire,
    DépôtHistoriqueEnMémoire,
    StockageImageEnMémoire,
)
from tests.modules.auth.conftest import DépôtRefreshTokenEnMémoire, DépôtUtilisateurEnMémoire
from tests.modules.ratelimit.conftest import RateLimiterPortEnMémoire

from composition.app import create_app
from modules.analyse.ports.cache import CachePort
from modules.analyse.ports.generateur_ia import GenerateurIAPort
from modules.analyse.ports.historique import DépôtHistoriquePort
from modules.analyse.ports.stockage_image import StockageImagePort
from modules.auth.ports.depot_refresh_token import DépôtRefreshTokenPort
from modules.auth.ports.depot_utilisateur import DépôtUtilisateurPort
from modules.ia.adaptateurs.generateur_ia_factice import GenerateurIAFactice
from modules.ratelimit.ports.rate_limiter import RateLimiterPort
from shared.config import get_settings

MOT_DE_PASSE_ROBUSTE = "cheval-trombone-9"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    # Même montage que tests/modules/analyse/adaptateurs/test_analyse_api.py.
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
        app.state.registry.register(CachePort, CachePortEnMémoire())
        app.state.registry.register(GenerateurIAPort, GenerateurIAFactice())
        app.state.registry.register(StockageImagePort, StockageImageEnMémoire())
        app.state.registry.register(DépôtHistoriquePort, DépôtHistoriqueEnMémoire())
        app.state.registry.register(RateLimiterPort, RateLimiterPortEnMémoire())
        yield test_client

    get_settings.cache_clear()


def _access_token(client: TestClient, email: str) -> str:
    client.post("/auth/inscription", json={"email": email, "mot_de_passe": MOT_DE_PASSE_ROBUSTE})
    reponse = client.post(
        "/auth/connexion", json={"email": email, "mot_de_passe": MOT_DE_PASSE_ROBUSTE}
    )
    access_token: str = reponse.json()["access_token"]
    return access_token


def test_historique_sans_authentification_retourne_401(client: TestClient) -> None:
    reponse = client.get("/historique")

    assert reponse.status_code == 401
    assert reponse.json()["code"] == "non_authentifie"


def test_historique_authentifie_est_vide_au_depart(client: TestClient) -> None:
    access_token = _access_token(client, "vide@example.com")

    reponse = client.get("/historique", headers={"Authorization": f"Bearer {access_token}"})

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps == {"items": [], "total": 0, "page": 1, "page_size": 20}


def test_historique_liste_les_analyses_soumises_par_l_utilisateur_authentifie(
    client: TestClient,
) -> None:
    access_token = _access_token(client, "actif@example.com")
    en_tete = {"Authorization": f"Bearer {access_token}"}
    analyse = client.post(
        "/analyses",
        json={"texte": "mon profil github pour l'historique", "source_type": "github"},
        headers=en_tete,
    )
    assert analyse.status_code == 200

    reponse = client.get("/historique", headers=en_tete)

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["total"] == 1
    assert len(corps["items"]) == 1
    entree = corps["items"][0]
    assert entree["input_text"] == "mon profil github pour l'historique"
    # Lien vers `/analyse/[id]` côté front (K6, backlog.md) : `resultat_id`
    # doit correspondre à l'`id` renvoyé par `POST /analyses`.
    assert entree["resultat_id"] == analyse.json()["id"]


def test_historique_soumis_anonymement_n_apparait_pas(client: TestClient) -> None:
    client.post("/analyses", json={"texte": "texte anonyme non trace", "source_type": "autre"})
    access_token = _access_token(client, "sans.rapport@example.com")

    reponse = client.get("/historique", headers={"Authorization": f"Bearer {access_token}"})

    assert reponse.json()["total"] == 0


def test_historique_isole_entre_deux_comptes(client: TestClient) -> None:
    # Coeur du ticket H3 (agents.md §7 — isolation multi-tenant) :
    # `user_id` scope strictement l'historique, un compte ne voit jamais
    # celui d'un autre.
    premier_token = _access_token(client, "premier.historique@example.com")
    client.post(
        "/analyses",
        json={"texte": "texte du premier compte", "source_type": "autre"},
        headers={"Authorization": f"Bearer {premier_token}"},
    )

    second_token = _access_token(client, "second.historique@example.com")
    reponse = client.get("/historique", headers={"Authorization": f"Bearer {second_token}"})

    assert reponse.json()["total"] == 0


def test_historique_est_pagine(client: TestClient) -> None:
    access_token = _access_token(client, "pagine@example.com")
    en_tete = {"Authorization": f"Bearer {access_token}"}
    for i in range(3):
        client.post(
            "/analyses",
            json={"texte": f"texte historique distinct {i}", "source_type": "autre"},
            headers=en_tete,
        )

    premiere_page = client.get("/historique?page=1&page_size=2", headers=en_tete)
    seconde_page = client.get("/historique?page=2&page_size=2", headers=en_tete)

    assert premiere_page.json()["total"] == 3
    assert len(premiere_page.json()["items"]) == 2
    assert len(seconde_page.json()["items"]) == 1
    # Pas de chevauchement entre les deux pages.
    ids_premiere = {item["id"] for item in premiere_page.json()["items"]}
    ids_seconde = {item["id"] for item in seconde_page.json()["items"]}
    assert ids_premiere.isdisjoint(ids_seconde)


def test_historique_page_size_hors_bornes_retourne_422(client: TestClient) -> None:
    access_token = _access_token(client, "bornes@example.com")

    reponse = client.get(
        "/historique?page_size=101", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert reponse.status_code == 422
