import uuid
from datetime import UTC, datetime

import pytest
from tests.modules.analyse.conftest import CachePortEnMémoire, StockageImageEnMémoire

from modules.analyse.application.executer_job_generation import ExecuterJobGeneration
from modules.analyse.domaine.analyse import Analyse, SourceAnalyse, StatutAnalyse
from modules.analyse.ports.generateur_ia import GenerateurIAPort

# Corps du job (F1) exécuté par le worker (F2, backlog.md) une fois le job
# reçu — que ce soit en synchrone (`FileJobsEnProcessusImmediat`, dev) ou
# après réception d'une tâche Cloud Tasks (`FileJobsCloudTasks` + endpoint
# interne du worker, F3, prod). Ces tests couvrent directement les deux
# transitions que le worker doit garantir (backlog.md F2) : `done` après
# une génération réussie, `failed` — sans jamais laisser la ligne bloquée
# en `pending` — après une génération en échec.


class _GenerateurIAEnMémoire(GenerateurIAPort):
    def __init__(self) -> None:
        self.appels_texte = 0
        self.appels_image = 0

    async def generer_texte(self, texte_source: str, source: SourceAnalyse) -> str:
        self.appels_texte += 1
        return f"résultat pour: {texte_source}"

    async def generer_image(self, texte_resultat: str) -> bytes:
        self.appels_image += 1
        return b"image"


class _GenerateurIAEnEchec(GenerateurIAPort):
    async def generer_texte(self, texte_source: str, source: SourceAnalyse) -> str:
        raise RuntimeError("panne fournisseur")

    async def generer_image(self, texte_resultat: str) -> bytes:
        raise RuntimeError("panne fournisseur")


def _analyse_pending() -> Analyse:
    return Analyse(
        id=uuid.uuid4(),
        texte_source="mon profil github",
        source=SourceAnalyse.GITHUB,
        statut=StatutAnalyse.PENDING,
        created_at=datetime.now(UTC),
    )


async def test_executer_marque_l_analyse_done_avec_le_resultat() -> None:
    cache = CachePortEnMémoire()
    generateur_ia = _GenerateurIAEnMémoire()
    stockage_image = StockageImageEnMémoire()
    job = ExecuterJobGeneration(
        cache=cache, generateur_ia=generateur_ia, stockage_image=stockage_image
    )
    analyse = _analyse_pending()
    await cache.inserer_si_absent(analyse)

    resultat = await job.executer(analyse)

    assert resultat.statut is StatutAnalyse.DONE
    assert resultat.resultat_texte == "résultat pour: mon profil github"
    assert resultat.resultat_image_url == f"memoire://{analyse.id}"
    assert generateur_ia.appels_texte == 1
    assert generateur_ia.appels_image == 1

    relue = await cache.obtenir_par_id(analyse.id)
    assert relue is not None
    assert relue.statut is StatutAnalyse.DONE


async def test_executer_marque_l_analyse_failed_et_propage_l_exception() -> None:
    # Filet de sécurité (agents.md §3, dégradation gracieuse — complété par
    # le circuit breaker en amont, E4) : une ligne ne doit jamais rester
    # bloquée en `pending` après l'échec d'un job, quel que soit le worker
    # (dev synchrone ou F3, prod) qui a exécuté ce job.
    cache = CachePortEnMémoire()
    job = ExecuterJobGeneration(
        cache=cache, generateur_ia=_GenerateurIAEnEchec(), stockage_image=StockageImageEnMémoire()
    )
    analyse = _analyse_pending()
    await cache.inserer_si_absent(analyse)

    with pytest.raises(RuntimeError, match="panne fournisseur"):
        await job.executer(analyse)

    relue = await cache.obtenir_par_id(analyse.id)
    assert relue is not None
    assert relue.statut is StatutAnalyse.FAILED
