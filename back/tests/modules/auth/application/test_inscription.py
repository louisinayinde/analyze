import pytest
from tests.modules.auth.conftest import DépôtUtilisateurEnMémoire

from modules.auth.adaptateurs.hacheur_argon2id import HacheurArgon2id
from modules.auth.application.inscription import InscrireUtilisateur
from shared.errors import ConflitRessource, EntreeInvalide

MOT_DE_PASSE_ROBUSTE = "cheval-trombone-9"


@pytest.fixture
def inscrire_utilisateur() -> tuple[InscrireUtilisateur, DépôtUtilisateurEnMémoire]:
    depot = DépôtUtilisateurEnMémoire()
    return InscrireUtilisateur(depot=depot, hacheur=HacheurArgon2id()), depot


async def test_inscription_nominale_hache_le_mot_de_passe_et_normalise_email(
    inscrire_utilisateur: tuple[InscrireUtilisateur, DépôtUtilisateurEnMémoire],
) -> None:
    use_case, depot = inscrire_utilisateur

    utilisateur = await use_case.executer("Nouvel.User@Example.COM", MOT_DE_PASSE_ROBUSTE)

    assert utilisateur.email == "nouvel.user@example.com"
    assert utilisateur.password_hash != MOT_DE_PASSE_ROBUSTE
    assert HacheurArgon2id().verifier(MOT_DE_PASSE_ROBUSTE, utilisateur.password_hash)
    assert await depot.trouver_par_email("nouvel.user@example.com") == utilisateur


async def test_inscription_rejette_un_email_invalide(
    inscrire_utilisateur: tuple[InscrireUtilisateur, DépôtUtilisateurEnMémoire],
) -> None:
    use_case, _ = inscrire_utilisateur

    with pytest.raises(EntreeInvalide):
        await use_case.executer("pas-un-email", MOT_DE_PASSE_ROBUSTE)


@pytest.mark.parametrize(
    "mot_de_passe",
    [
        "court1",  # trop court
        "1234567890123",  # uniquement des chiffres
        "password",  # trop courant
        "nouvel.user",  # basé sur la partie locale de l'email
    ],
)
async def test_inscription_rejette_un_mot_de_passe_faible(
    inscrire_utilisateur: tuple[InscrireUtilisateur, DépôtUtilisateurEnMémoire],
    mot_de_passe: str,
) -> None:
    use_case, _ = inscrire_utilisateur

    with pytest.raises(EntreeInvalide):
        await use_case.executer("nouvel.user@example.com", mot_de_passe)


async def test_inscription_avec_email_deja_pris_renvoie_un_message_generique(
    inscrire_utilisateur: tuple[InscrireUtilisateur, DépôtUtilisateurEnMémoire],
) -> None:
    use_case, _ = inscrire_utilisateur
    await use_case.executer("deja.pris@example.com", MOT_DE_PASSE_ROBUSTE)

    with pytest.raises(ConflitRessource) as exc_info:
        await use_case.executer("deja.pris@example.com", "autre-mot-de-passe-9")

    # Pas d'énumération (agents.md §7) : le message ne doit jamais confirmer
    # explicitement que l'email est déjà pris.
    assert "existe déjà" not in exc_info.value.message
    assert "déjà pris" not in exc_info.value.message
