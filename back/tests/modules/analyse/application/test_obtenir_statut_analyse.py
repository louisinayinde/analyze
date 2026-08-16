import uuid
from datetime import UTC, datetime

import pytest
from tests.modules.analyse.conftest import CachePortEnMémoire

from modules.analyse.application.obtenir_statut_analyse import ObtenirStatutAnalyse
from modules.analyse.domaine.analyse import Analyse, SourceAnalyse, StatutAnalyse
from shared.errors import RessourceIntrouvable


@pytest.fixture
def cache() -> CachePortEnMémoire:
    return CachePortEnMémoire()


@pytest.fixture
def obtenir_statut(cache: CachePortEnMémoire) -> ObtenirStatutAnalyse:
    return ObtenirStatutAnalyse(cache=cache)


async def test_analyse_pending_retourne_le_statut_pending_sans_resultat(
    obtenir_statut: ObtenirStatutAnalyse, cache: CachePortEnMémoire
) -> None:
    en_cours = Analyse(
        id=uuid.uuid4(),
        texte_source="Mon profil GitHub",
        source=SourceAnalyse.GITHUB,
        statut=StatutAnalyse.PENDING,
        created_at=datetime.now(UTC),
    )
    await cache.inserer_si_absent(en_cours)

    resultat = await obtenir_statut.executer(en_cours.id)

    assert resultat.statut is StatutAnalyse.PENDING
    assert resultat.resultat_texte is None
    assert resultat.resultat_image_url is None


async def test_analyse_done_retourne_le_resultat(
    obtenir_statut: ObtenirStatutAnalyse, cache: CachePortEnMémoire
) -> None:
    terminee = Analyse(
        id=uuid.uuid4(),
        texte_source="Mon profil GitHub",
        source=SourceAnalyse.GITHUB,
        statut=StatutAnalyse.PENDING,
        created_at=datetime.now(UTC),
    )
    await cache.inserer_si_absent(terminee)
    await cache.marquer_termine(
        Analyse(
            id=terminee.id,
            texte_source=terminee.texte_source,
            source=terminee.source,
            statut=StatutAnalyse.PENDING,
            created_at=terminee.created_at,
            resultat_texte="ton roast est prêt",
            resultat_image_url="memoire://roast.png",
        )
    )

    resultat = await obtenir_statut.executer(terminee.id)

    assert resultat.statut is StatutAnalyse.DONE
    assert resultat.resultat_texte == "ton roast est prêt"
    assert resultat.resultat_image_url == "memoire://roast.png"


async def test_analyse_failed_retourne_le_statut_failed(
    obtenir_statut: ObtenirStatutAnalyse, cache: CachePortEnMémoire
) -> None:
    en_echec = Analyse(
        id=uuid.uuid4(),
        texte_source="texte qui échoue",
        source=SourceAnalyse.BIO,
        statut=StatutAnalyse.PENDING,
        created_at=datetime.now(UTC),
    )
    await cache.inserer_si_absent(en_echec)
    await cache.marquer_echec(en_echec)

    resultat = await obtenir_statut.executer(en_echec.id)

    assert resultat.statut is StatutAnalyse.FAILED


async def test_id_inconnu_leve_ressource_introuvable(
    obtenir_statut: ObtenirStatutAnalyse,
) -> None:
    # Chemin d'échec explicitement listé en exemple par agents.md §6 — ne
    # pas le sauter : un `job_id` mal formé ou expiré ne doit jamais faire
    # planter le polling client, mais renvoyer une erreur exploitable.
    with pytest.raises(RessourceIntrouvable):
        await obtenir_statut.executer(uuid.uuid4())
