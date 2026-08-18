import uuid
from datetime import UTC, datetime

import pytest
from tests.modules.auth.conftest import DépôtUtilisateurEnMémoire

from modules.auth.adaptateurs.hacheur_argon2id import HacheurArgon2id
from modules.auth.application.supprimer_compte import SupprimerCompte
from modules.auth.domaine.utilisateur import Utilisateur
from shared.errors import NonAuthentifie

MOT_DE_PASSE = "cheval-trombone-9"


async def _depot_avec_un_utilisateur(
    hacheur: HacheurArgon2id,
) -> tuple[DépôtUtilisateurEnMémoire, Utilisateur]:
    depot = DépôtUtilisateurEnMémoire()
    utilisateur = Utilisateur(
        id=uuid.uuid4(),
        email="a.supprimer@example.com",
        password_hash=hacheur.hacher(MOT_DE_PASSE),
        created_at=datetime.now(UTC),
    )
    await depot.creer(utilisateur)
    return depot, utilisateur


async def test_suppression_nominale_supprime_le_compte() -> None:
    hacheur = HacheurArgon2id()
    depot, utilisateur = await _depot_avec_un_utilisateur(hacheur)
    use_case = SupprimerCompte(depot=depot, hacheur=hacheur)

    await use_case.executer(utilisateur.id, MOT_DE_PASSE)

    assert await depot.trouver_par_id(utilisateur.id) is None


async def test_mot_de_passe_incorrect_leve_non_authentifie_et_ne_supprime_rien() -> None:
    # Coeur du ticket H3 (agents.md §7 — vérification renforcée) : un JWT
    # valide seul ne doit pas suffire à supprimer le compte.
    hacheur = HacheurArgon2id()
    depot, utilisateur = await _depot_avec_un_utilisateur(hacheur)
    use_case = SupprimerCompte(depot=depot, hacheur=hacheur)

    with pytest.raises(NonAuthentifie):
        await use_case.executer(utilisateur.id, "mauvais-mot-de-passe-9")

    assert await depot.trouver_par_id(utilisateur.id) is not None


async def test_utilisateur_deja_supprime_leve_non_authentifie() -> None:
    hacheur = HacheurArgon2id()
    depot = DépôtUtilisateurEnMémoire()
    use_case = SupprimerCompte(depot=depot, hacheur=hacheur)

    with pytest.raises(NonAuthentifie):
        await use_case.executer(uuid.uuid4(), MOT_DE_PASSE)
