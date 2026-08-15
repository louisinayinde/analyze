import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from tests.modules.auth.conftest import DépôtRefreshTokenEnMémoire, DépôtUtilisateurEnMémoire

from modules.auth.adaptateurs.emetteur_jwt import ALGORITHME, EmetteurJWT
from modules.auth.adaptateurs.hacheur_argon2id import HacheurArgon2id
from modules.auth.application.connexion import _MESSAGE_ECHEC_GENERIQUE, ConnecterUtilisateur
from modules.auth.domaine.utilisateur import Utilisateur
from shared.errors import NonAuthentifie

MOT_DE_PASSE_ROBUSTE = "cheval-trombone-9"
CLE_SIGNATURE = "cle-de-test-suffisamment-longue-32c"

FixtureConnexion = tuple[
    ConnecterUtilisateur, DépôtUtilisateurEnMémoire, DépôtRefreshTokenEnMémoire
]


@pytest.fixture
def connecter_utilisateur() -> FixtureConnexion:
    depot = DépôtUtilisateurEnMémoire()
    depot_refresh = DépôtRefreshTokenEnMémoire()
    emetteur = EmetteurJWT(
        cle_signature=CLE_SIGNATURE,
        duree_access=timedelta(minutes=15),
        duree_refresh=timedelta(days=30),
    )
    use_case = ConnecterUtilisateur(
        depot=depot, hacheur=HacheurArgon2id(), emetteur=emetteur, depot_refresh=depot_refresh
    )
    return use_case, depot, depot_refresh


async def _creer_utilisateur(
    depot: DépôtUtilisateurEnMémoire, email: str, mot_de_passe: str
) -> Utilisateur:
    utilisateur = Utilisateur(
        id=uuid.uuid4(),
        email=email,
        password_hash=HacheurArgon2id().hacher(mot_de_passe),
        created_at=datetime.now(UTC),
    )
    return await depot.creer(utilisateur)


async def test_connexion_nominale_emet_des_jetons_et_met_a_jour_derniere_connexion(
    connecter_utilisateur: FixtureConnexion,
) -> None:
    use_case, depot, _ = connecter_utilisateur
    utilisateur = await _creer_utilisateur(depot, "nouvel.user@example.com", MOT_DE_PASSE_ROBUSTE)

    jetons = await use_case.executer("nouvel.user@example.com", MOT_DE_PASSE_ROBUSTE)

    claims = jwt.decode(jetons.access_token, CLE_SIGNATURE, algorithms=[ALGORITHME])
    assert claims["sub"] == str(utilisateur.id)
    assert jetons.expires_in == 15 * 60
    assert utilisateur.id in depot.dernieres_connexions


async def test_connexion_normalise_la_casse_de_lemail(
    connecter_utilisateur: FixtureConnexion,
) -> None:
    use_case, depot, _ = connecter_utilisateur
    await _creer_utilisateur(depot, "nouvel.user@example.com", MOT_DE_PASSE_ROBUSTE)

    jetons = await use_case.executer("Nouvel.User@Example.COM", MOT_DE_PASSE_ROBUSTE)

    assert jetons.access_token


async def test_connexion_avec_email_inconnu_leve_non_authentifie(
    connecter_utilisateur: FixtureConnexion,
) -> None:
    use_case, _, _ = connecter_utilisateur

    with pytest.raises(NonAuthentifie) as exc_info:
        await use_case.executer("inconnu@example.com", MOT_DE_PASSE_ROBUSTE)

    assert exc_info.value.message == _MESSAGE_ECHEC_GENERIQUE


async def test_connexion_avec_mot_de_passe_incorrect_leve_non_authentifie(
    connecter_utilisateur: FixtureConnexion,
) -> None:
    use_case, depot, _ = connecter_utilisateur
    await _creer_utilisateur(depot, "nouvel.user@example.com", MOT_DE_PASSE_ROBUSTE)

    with pytest.raises(NonAuthentifie) as exc_info:
        await use_case.executer("nouvel.user@example.com", "mauvais-mot-de-passe-9")

    # Même message que pour un email inconnu : pas d'énumération
    # d'utilisateurs, y compris via le contenu du message d'erreur
    # (agents.md §7).
    assert exc_info.value.message == _MESSAGE_ECHEC_GENERIQUE


async def test_connexion_echouee_ne_met_pas_a_jour_derniere_connexion(
    connecter_utilisateur: FixtureConnexion,
) -> None:
    use_case, depot, _ = connecter_utilisateur
    utilisateur = await _creer_utilisateur(depot, "nouvel.user@example.com", MOT_DE_PASSE_ROBUSTE)

    with pytest.raises(NonAuthentifie):
        await use_case.executer("nouvel.user@example.com", "mauvais-mot-de-passe-9")

    assert utilisateur.id not in depot.dernieres_connexions


async def test_connexion_nominale_ouvre_une_famille_de_refresh(
    connecter_utilisateur: FixtureConnexion,
) -> None:
    # C6 : sans cet enregistrement initial, le premier `/auth/refresh`
    # suivant ce login ne trouverait aucun `jti` connu en base et la
    # rotation serait impossible dès le départ.
    use_case, depot, depot_refresh = connecter_utilisateur
    await _creer_utilisateur(depot, "nouvel.user@example.com", MOT_DE_PASSE_ROBUSTE)

    jetons = await use_case.executer("nouvel.user@example.com", MOT_DE_PASSE_ROBUSTE)

    enregistrement = await depot_refresh.trouver_par_jti(jetons.refresh_jti)
    assert enregistrement is not None
    assert enregistrement.est_valide
