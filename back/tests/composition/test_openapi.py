from typing import Any

import pytest

from composition.app import create_app
from shared.config import get_settings


@pytest.fixture
def schema(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    # `app.openapi()` ne fait que construire le schéma depuis les routes
    # montées : pas besoin de lifespan ni de connexion Postgres réelle
    # (contrairement aux tests qui passent par `TestClient`, ex.
    # tests/composition/test_worker.py) — les variables d'environnement ne
    # servent qu'à satisfaire `Settings` au moment de `create_app()`.
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    _dsn_test = "postgresql+asyncpg://test:test@localhost:5432/test"  # pragma: allowlist secret
    monkeypatch.setenv("DATABASE_URL", _dsn_test)
    monkeypatch.setenv("JWT_SIGNING_KEY", "cle-de-test-suffisamment-longue-32c")
    get_settings.cache_clear()

    app = create_app()
    result = app.openapi()

    get_settings.cache_clear()
    return result


def test_openapi_declare_les_tags_auth_et_analyse(schema: dict[str, Any]) -> None:
    # H1 (backlog.md) : le contrat devient la source de vérité (agents.md
    # §3) — sans tags décrits, `/docs` et le futur client généré (H2) ne
    # regroupent pas les endpoints par domaine métier.
    noms_tags = {tag["name"] for tag in schema["tags"]}
    assert noms_tags == {"auth", "analyse"}
    assert all(tag["description"] for tag in schema["tags"])


@pytest.mark.parametrize(
    ("chemin", "methode", "codes_erreur_attendus"),
    [
        ("/auth/inscription", "post", {"409", "422"}),
        ("/auth/connexion", "post", {"401"}),
        ("/auth/refresh", "post", {"401"}),
        ("/analyses", "post", {"422", "429"}),
        ("/analyses/{analyse_id}/statut", "get", {"404"}),
    ],
)
def test_chaque_endpoint_documente_ses_erreurs_reelles(
    schema: dict[str, Any], chemin: str, methode: str, codes_erreur_attendus: set[str]
) -> None:
    # Chaque code correspond à une exception `ErreurDomaine` réellement
    # levée sur ce chemin (shared/errors.py) — pas une liste générique de
    # statuts HTTP possibles en théorie (voir shared/openapi.responses_erreur).
    operation = schema["paths"][chemin][methode]
    assert operation["summary"]
    codes_presents = set(operation["responses"].keys())
    assert codes_erreur_attendus <= codes_presents

    for code in codes_erreur_attendus:
        exemple = operation["responses"][code]["content"]["application/json"]["example"]
        assert exemple["code"]
        assert exemple["message"]
        assert exemple["correlation_id"]


def test_requetes_et_reponses_portent_un_exemple(schema: dict[str, Any]) -> None:
    # Un schéma sans exemple oblige le lecteur (humain ou client généré en
    # H2) à deviner la forme d'un payload à partir des seuls types Pydantic.
    schemas = schema["components"]["schemas"]
    for nom in (
        "InscriptionRequete",
        "ConnexionRequete",
        "JetonsReponse",
        "UtilisateurReponse",
        "AnalyseRequete",
    ):
        assert "example" in schemas[nom]
