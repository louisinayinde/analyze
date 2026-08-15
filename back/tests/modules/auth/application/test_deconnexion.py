import uuid
from datetime import UTC, datetime, timedelta

import pytest
from tests.modules.auth.conftest import DépôtRefreshTokenEnMémoire

from modules.auth.adaptateurs.emetteur_jwt import EmetteurJWT
from modules.auth.application.deconnexion import DeconnecterUtilisateur
from modules.auth.domaine.enregistrement_refresh import EnregistrementRefresh

CLE_SIGNATURE = "cle-de-test-suffisamment-longue-32c"

FixtureDeconnexion = tuple[DeconnecterUtilisateur, EmetteurJWT, DépôtRefreshTokenEnMémoire]


@pytest.fixture
def deconnecter_utilisateur() -> FixtureDeconnexion:
    emetteur = EmetteurJWT(
        cle_signature=CLE_SIGNATURE,
        duree_access=timedelta(minutes=15),
        duree_refresh=timedelta(days=30),
    )
    depot_refresh = DépôtRefreshTokenEnMémoire()
    return (
        DeconnecterUtilisateur(emetteur=emetteur, depot_refresh=depot_refresh),
        emetteur,
        depot_refresh,
    )


async def _connecter(
    emetteur: EmetteurJWT, depot_refresh: DépôtRefreshTokenEnMémoire, user_id: uuid.UUID
) -> str:
    """Simule ce que fait `ConnecterUtilisateur` (C4) : ouvre une famille initiale."""
    jetons = emetteur.emettre_jetons(user_id)
    await depot_refresh.creer(
        EnregistrementRefresh(
            jti=jetons.refresh_jti,
            family_id=uuid.uuid4(),
            user_id=user_id,
            created_at=datetime.now(UTC),
            expires_at=jetons.refresh_expires_at,
        )
    )
    return jetons.refresh_token


async def test_deconnexion_nominale_revoque_uniquement_le_refresh_presente(
    deconnecter_utilisateur: FixtureDeconnexion,
) -> None:
    use_case, emetteur, depot_refresh = deconnecter_utilisateur
    user_id = uuid.uuid4()
    refresh_token = await _connecter(emetteur, depot_refresh, user_id)
    donnees = emetteur.decoder_refresh(refresh_token)

    await use_case.executer(refresh_token)

    enregistrement = await depot_refresh.trouver_par_jti(donnees.jti)
    assert enregistrement is not None
    assert enregistrement.revoked_at is not None
    assert not enregistrement.est_valide


async def test_deconnexion_ne_revoque_pas_les_autres_membres_de_la_famille(
    deconnecter_utilisateur: FixtureDeconnexion,
) -> None:
    # Coeur du ticket C7 : contrairement au rejeu (C6), une déconnexion
    # volontaire n'est pas un signal de vol — seul le jeton présenté doit
    # être invalidé, pas toute la famille.
    use_case, emetteur, depot_refresh = deconnecter_utilisateur
    user_id = uuid.uuid4()
    family_id = uuid.uuid4()
    refresh_token = await _connecter(emetteur, depot_refresh, user_id)
    donnees = emetteur.decoder_refresh(refresh_token)
    # Un second membre de la même famille, comme le ferait une rotation.
    autre_jetons = emetteur.emettre_jetons(user_id)
    await depot_refresh.creer(
        EnregistrementRefresh(
            jti=autre_jetons.refresh_jti,
            family_id=family_id,
            user_id=user_id,
            created_at=datetime.now(UTC),
            expires_at=autre_jetons.refresh_expires_at,
        )
    )

    await use_case.executer(refresh_token)

    autre_enregistrement = await depot_refresh.trouver_par_jti(autre_jetons.refresh_jti)
    assert autre_enregistrement is not None
    assert autre_enregistrement.revoked_at is None
    assert donnees.jti != autre_jetons.refresh_jti


async def test_deconnexion_avec_refresh_deja_invalide_ne_leve_pas_derreur(
    deconnecter_utilisateur: FixtureDeconnexion,
) -> None:
    # Idempotence (agents.md §6) : un refresh structurellement invalide (mal
    # formé, signature erronée, expiré) ne doit pas faire échouer la
    # déconnexion — le client obtient de toute façon ce qu'il voulait.
    use_case, _, _ = deconnecter_utilisateur

    await use_case.executer("pas-un-jwt")


async def test_deconnexion_avec_refresh_de_jti_inconnu_ne_leve_pas_derreur(
    deconnecter_utilisateur: FixtureDeconnexion,
) -> None:
    use_case, emetteur, _ = deconnecter_utilisateur
    jetons_orphelins = emetteur.emettre_jetons(uuid.uuid4())

    await use_case.executer(jetons_orphelins.refresh_token)


async def test_deconnexion_avec_un_access_token_ne_leve_pas_derreur(
    deconnecter_utilisateur: FixtureDeconnexion,
) -> None:
    # Un access token présenté ici échoue le contrôle du claim `type` dans
    # `decoder_refresh` (C6) — traité comme n'importe quel jeton invalide :
    # pas d'erreur, rien à révoquer.
    use_case, emetteur, _ = deconnecter_utilisateur
    jetons = emetteur.emettre_jetons(uuid.uuid4())

    await use_case.executer(jetons.access_token)


async def test_deconnexion_appelee_deux_fois_sur_le_meme_jeton_reste_sans_erreur(
    deconnecter_utilisateur: FixtureDeconnexion,
) -> None:
    use_case, emetteur, depot_refresh = deconnecter_utilisateur
    refresh_token = await _connecter(emetteur, depot_refresh, uuid.uuid4())

    await use_case.executer(refresh_token)
    await use_case.executer(refresh_token)
