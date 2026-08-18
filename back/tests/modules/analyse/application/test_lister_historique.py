import uuid

from tests.modules.analyse.conftest import DépôtHistoriqueEnMémoire

from modules.analyse.application.lister_historique import ListerHistorique


async def test_ne_retourne_que_les_entrees_de_l_utilisateur_demande() -> None:
    depot = DépôtHistoriqueEnMémoire()
    premier_user, second_user = uuid.uuid4(), uuid.uuid4()
    await depot.enregistrer(premier_user, uuid.uuid4(), "texte du premier user")
    await depot.enregistrer(second_user, uuid.uuid4(), "texte du second user")
    use_case = ListerHistorique(depot=depot)

    entrees, total = await use_case.executer(premier_user, page=1, page_size=10)

    # Coeur du ticket H3 (agents.md §7) : le scoping par `user_id` isole
    # bien les comptes, même sur un dépôt qui contient les deux.
    assert total == 1
    assert entrees[0].input_text == "texte du premier user"


async def test_page_vide_au_dela_du_total() -> None:
    depot = DépôtHistoriqueEnMémoire()
    user_id = uuid.uuid4()
    await depot.enregistrer(user_id, uuid.uuid4(), "unique entrée")
    use_case = ListerHistorique(depot=depot)

    entrees, total = await use_case.executer(user_id, page=2, page_size=10)

    assert entrees == []
    assert total == 1
