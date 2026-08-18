import asyncio
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from tests.modules.analyse.conftest import (
    CachePortEnMémoire,
    DépôtHistoriqueEnMémoire,
    StockageImageEnMémoire,
)
from tests.modules.ratelimit.conftest import RateLimiterPortEnMémoire

from composition.app import create_app
from modules.analyse.domaine.analyse import SourceAnalyse
from modules.analyse.ports.cache import CachePort
from modules.analyse.ports.generateur_ia import GenerateurIAPort
from modules.analyse.ports.historique import DépôtHistoriquePort
from modules.analyse.ports.stockage_image import StockageImagePort
from modules.ratelimit.ports.rate_limiter import RateLimiterPort
from shared.config import get_settings


class GenerateurIALenteFactice(GenerateurIAPort):
    """Faux `GenerateurIAPort` qui simule la latence réseau d'un vrai appel
    LLM, dédié au test de concurrence (D6).

    `GenerateurIAFactice` (D1) et `CachePortEnMémoire` (D3) n'ont aucun
    point de suspension (`await`) interne : deux coroutines lancées « en
    même temps » via `asyncio.gather` mais bâties uniquement sur ces
    doubles s'exécuteraient en réalité l'une après l'autre sans jamais se
    croiser (la boucle asyncio ne change de tâche qu'à un point de
    suspension réel), et le test ne prouverait rien de plus que l'appel
    séquentiel déjà couvert par
    `test_analyses_meme_texte_deux_fois_ne_declenche_qu_un_seul_appel_ia`
    (D4). Le délai ci-dessous force la fenêtre de course réaliste que
    projets.md décrit : la ligne `pending` (écriture DB, rapide) est déjà
    posée quand une seconde requête concurrente arrive, alors que la
    génération IA (réseau, lente) est encore en cours.
    """

    def __init__(self, delai_secondes: float = 0.05) -> None:
        self.appels_texte = 0
        self.appels_image = 0
        self._delai = delai_secondes

    async def generer_texte(self, texte_source: str, source: SourceAnalyse) -> str:
        self.appels_texte += 1
        await asyncio.sleep(self._delai)
        return f"analyse factice lente pour {texte_source.strip()}"

    async def generer_image(self, texte_resultat: str) -> bytes:
        self.appels_image += 1
        await asyncio.sleep(self._delai / 5)
        return b"image-factice-lente"


FixtureConcurrence = tuple[AsyncClient, GenerateurIALenteFactice]


@pytest.fixture
async def client_concurrent(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[FixtureConcurrence]:
    # Même montage que `tests/modules/analyse/adaptateurs/test_analyse_api.py` :
    # les variables d'environnement ne servent qu'à satisfaire `Settings`,
    # aucune connexion Postgres réelle n'est ouverte — `CachePort` et
    # `GenerateurIAPort` sont remplacés par des doubles en mémoire juste
    # après construction de l'app, avant toute requête.
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    _dsn_test = "postgresql+asyncpg://test:test@localhost:5432/test"  # pragma: allowlist secret
    monkeypatch.setenv("DATABASE_URL", _dsn_test)
    monkeypatch.setenv("JWT_SIGNING_KEY", "cle-de-test-suffisamment-longue-32c")
    # Quota IP (G2) largement au-dessus du nombre de requêtes simultanées
    # envoyées par ces tests (jusqu'à 10) : ce fichier prouve la déduplication
    # du cache sous course, pas le rate limiting (déjà couvert par
    # tests/modules/analyse/adaptateurs/test_analyse_api.py) — la capacité
    # par défaut (5) ferait échouer ces requêtes anonymes sur un motif sans
    # rapport avec ce que le test vérifie.
    monkeypatch.setenv("RATE_LIMIT_ANALYSES_IP_CAPACITE", "50")
    get_settings.cache_clear()

    app = create_app()
    generateur_ia = GenerateurIALenteFactice()
    app.state.registry.register(CachePort, CachePortEnMémoire())
    app.state.registry.register(GenerateurIAPort, generateur_ia)
    app.state.registry.register(StockageImagePort, StockageImageEnMémoire())
    app.state.registry.register(DépôtHistoriquePort, DépôtHistoriqueEnMémoire())
    # `LimiteurDebitPostgres` (câblé par `create_app()`, G1) remplacé par le
    # double en mémoire (G2) : même raison que
    # tests/modules/analyse/adaptateurs/test_analyse_api.py — aucune base
    # Postgres réelle n'est démarrée pour ces tests.
    app.state.registry.register(RateLimiterPort, RateLimiterPortEnMémoire())

    # `httpx.AsyncClient` (et non `TestClient`, synchrone) : seul un client
    # asynchrone permet de lancer deux requêtes *réellement* en même temps
    # via `asyncio.gather`, plutôt que l'une après l'autre.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, generateur_ia

    get_settings.cache_clear()


async def test_deux_requetes_simultanees_meme_texte_ne_declenchent_qu_un_seul_appel_ia(
    client_concurrent: FixtureConcurrence,
) -> None:
    """D6 — le test qui prouve la promesse.

    Contrairement à
    `test_analyses_meme_texte_deux_fois_ne_declenche_qu_un_seul_appel_ia`
    (D4, deux appels HTTP strictement séquentiels : le second ne part
    qu'une fois le premier entièrement terminé), ce test lance les deux
    requêtes via `asyncio.gather` : les deux coroutines démarrent avant
    qu'aucune des deux n'ait terminé. C'est l'argument vendu au recruteur
    (« je ne paie le LLM qu'une fois par input ») qui est vérifié ici, pas
    seulement le cas où les requêtes s'enchaînent proprement.
    """
    client, generateur_ia = client_concurrent
    corps_requete = {
        "texte": "deux utilisateurs collent le même texte pile en même temps",
        "source_type": "autre",
    }

    premiere, seconde = await asyncio.gather(
        client.post("/analyses", json=corps_requete),
        client.post("/analyses", json=corps_requete),
    )

    assert premiere.status_code in (200, 202)
    assert seconde.status_code in (200, 202)
    id_premiere = premiere.json().get("id") or premiere.json().get("job_id")
    id_seconde = seconde.json().get("id") or seconde.json().get("job_id")
    # Une seule ligne de cache créée pour ce texte, peu importe laquelle des
    # deux requêtes est arrivée « première » côté serveur.
    assert id_premiere == id_seconde
    # Coeur de la promesse (projets.md, backlog.md D6) : un seul appel au
    # port IA déclenché, quel que soit l'entrelacement réel des deux
    # requêtes concurrentes.
    assert generateur_ia.appels_texte == 1
    assert generateur_ia.appels_image == 1


async def test_dix_requetes_simultanees_meme_texte_ne_declenchent_qu_un_seul_appel_ia(
    client_concurrent: FixtureConcurrence,
) -> None:
    """Renforce D6 : la garantie tient sous une course à N > 2 appelants,
    pas seulement dans le cas particulier de deux requêtes.
    """
    client, generateur_ia = client_concurrent
    corps_requete = {
        "texte": "dix utilisateurs collent le même texte en rafale",
        "source_type": "autre",
    }

    reponses = await asyncio.gather(
        *(client.post("/analyses", json=corps_requete) for _ in range(10))
    )

    assert all(reponse.status_code in (200, 202) for reponse in reponses)
    assert generateur_ia.appels_texte == 1
    assert generateur_ia.appels_image == 1


async def test_deux_requetes_simultanees_textes_differents_declenchent_chacune_un_appel(
    client_concurrent: FixtureConcurrence,
) -> None:
    """Garde-fou symétrique à D6 : la protection de concurrence ne doit
    jamais fusionner deux inputs distincts (agents.md §2 — le cache doit
    rester correct, pas seulement économe).
    """
    client, generateur_ia = client_concurrent

    premiere, seconde = await asyncio.gather(
        client.post("/analyses", json={"texte": "premier texte distinct", "source_type": "autre"}),
        client.post("/analyses", json={"texte": "second texte distinct", "source_type": "autre"}),
    )

    assert premiere.status_code in (200, 202)
    assert seconde.status_code in (200, 202)
    assert generateur_ia.appels_texte == 2
