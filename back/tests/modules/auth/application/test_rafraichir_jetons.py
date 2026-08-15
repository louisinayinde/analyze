import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from tests.modules.auth.conftest import DépôtRefreshTokenEnMémoire

from modules.auth.adaptateurs.emetteur_jwt import ALGORITHME, EmetteurJWT
from modules.auth.application.rafraichir_jetons import (
    _MESSAGE_ECHEC_GENERIQUE,
    RafraichirJetons,
)
from modules.auth.domaine.enregistrement_refresh import EnregistrementRefresh
from modules.auth.domaine.jeton import RefreshTokenRejoue
from shared.errors import NonAuthentifie

CLE_SIGNATURE = "cle-de-test-suffisamment-longue-32c"

FixtureRafraichissement = tuple[RafraichirJetons, EmetteurJWT, DépôtRefreshTokenEnMémoire]


@pytest.fixture
def rafraichir_jetons() -> FixtureRafraichissement:
    emetteur = EmetteurJWT(
        cle_signature=CLE_SIGNATURE,
        duree_access=timedelta(minutes=15),
        duree_refresh=timedelta(days=30),
    )
    depot_refresh = DépôtRefreshTokenEnMémoire()
    return RafraichirJetons(emetteur=emetteur, depot_refresh=depot_refresh), emetteur, depot_refresh


async def _connecter(
    emetteur: EmetteurJWT, depot_refresh: DépôtRefreshTokenEnMémoire, user_id: uuid.UUID
) -> tuple[str, uuid.UUID]:
    """Simule ce que fait `ConnecterUtilisateur` (C4) : ouvre une famille initiale.

    Retourne le refresh token émis et l'identifiant de sa famille — pratique
    pour les tests qui doivent vérifier qu'une rotation reste dans la même
    famille, ou que toute la famille est bien révoquée sur rejeu.
    """
    jetons = emetteur.emettre_jetons(user_id)
    family_id = uuid.uuid4()
    await depot_refresh.creer(
        EnregistrementRefresh(
            jti=jetons.refresh_jti,
            family_id=family_id,
            user_id=user_id,
            created_at=datetime.now(UTC),
            expires_at=jetons.refresh_expires_at,
        )
    )
    return jetons.refresh_token, family_id


async def test_rotation_nominale_emet_une_nouvelle_paire_et_marque_lancien_jeton_utilise(
    rafraichir_jetons: FixtureRafraichissement,
) -> None:
    use_case, emetteur, depot_refresh = rafraichir_jetons
    user_id = uuid.uuid4()
    refresh_token, _ = await _connecter(emetteur, depot_refresh, user_id)
    ancien_jti = uuid.UUID(jwt.decode(refresh_token, CLE_SIGNATURE, algorithms=[ALGORITHME])["jti"])

    nouveaux_jetons = await use_case.executer(refresh_token)

    assert nouveaux_jetons.refresh_token != refresh_token
    claims = jwt.decode(nouveaux_jetons.access_token, CLE_SIGNATURE, algorithms=[ALGORITHME])
    assert claims["sub"] == str(user_id)

    ancien = await depot_refresh.trouver_par_jti(ancien_jti)
    assert ancien is not None
    assert ancien.used_at is not None
    assert not ancien.est_valide


async def test_rotation_nominale_reste_dans_la_meme_famille(
    rafraichir_jetons: FixtureRafraichissement,
) -> None:
    use_case, emetteur, depot_refresh = rafraichir_jetons
    refresh_token, family_id = await _connecter(emetteur, depot_refresh, uuid.uuid4())

    nouveaux_jetons = await use_case.executer(refresh_token)

    nouvel_enregistrement = await depot_refresh.trouver_par_jti(nouveaux_jetons.refresh_jti)
    assert nouvel_enregistrement is not None
    assert nouvel_enregistrement.family_id == family_id


async def test_un_refresh_rejoue_leve_refresh_token_rejoue_et_revoque_toute_la_famille(
    rafraichir_jetons: FixtureRafraichissement,
) -> None:
    # Coeur du ticket C6 : un refresh déjà consommé par une rotation
    # antérieure est représenté une seconde fois — signal de vol. Toute la
    # famille doit être invalidée, pas seulement le jeton rejoué.
    use_case, emetteur, depot_refresh = rafraichir_jetons
    refresh_token, _ = await _connecter(emetteur, depot_refresh, uuid.uuid4())

    premiere_rotation = await use_case.executer(refresh_token)

    with pytest.raises(RefreshTokenRejoue):
        await use_case.executer(refresh_token)

    # La nouvelle paire légitime issue de la première rotation est elle
    # aussi révoquée : toute la famille tombe, pas seulement le jeton rejoué.
    nouvel_enregistrement = await depot_refresh.trouver_par_jti(premiere_rotation.refresh_jti)
    assert nouvel_enregistrement is not None
    assert nouvel_enregistrement.revoked_at is not None
    assert not nouvel_enregistrement.est_valide


async def test_apres_rejeu_le_refresh_issu_de_la_rotation_legitime_est_aussi_rejete(
    rafraichir_jetons: FixtureRafraichissement,
) -> None:
    # Conséquence de la révocation de famille : même la paire "légitime"
    # émise par la première rotation ne doit plus permettre de rafraîchir.
    use_case, emetteur, depot_refresh = rafraichir_jetons
    refresh_token, _ = await _connecter(emetteur, depot_refresh, uuid.uuid4())

    premiere_rotation = await use_case.executer(refresh_token)
    with pytest.raises(RefreshTokenRejoue):
        await use_case.executer(refresh_token)

    with pytest.raises(RefreshTokenRejoue):
        await use_case.executer(premiere_rotation.refresh_token)


async def test_refresh_token_rejoue_porte_lidentite_pour_le_log_dalerte(
    rafraichir_jetons: FixtureRafraichissement,
) -> None:
    use_case, emetteur, depot_refresh = rafraichir_jetons
    user_id = uuid.uuid4()
    refresh_token, family_id = await _connecter(emetteur, depot_refresh, user_id)
    await use_case.executer(refresh_token)

    with pytest.raises(RefreshTokenRejoue) as exc_info:
        await use_case.executer(refresh_token)

    assert exc_info.value.user_id == user_id
    assert exc_info.value.family_id == family_id
    assert exc_info.value.code == "refresh_rejoue"


async def test_un_jeton_deja_revoque_est_traite_comme_un_rejeu(
    rafraichir_jetons: FixtureRafraichissement,
) -> None:
    # Un jeton jamais utilisé mais dont la famille a déjà été révoquée (ex.
    # sibling d'un rejeu précédent) doit aussi être rejeté comme un rejeu,
    # pas comme un simple jeton "inconnu".
    use_case, emetteur, depot_refresh = rafraichir_jetons
    refresh_token, family_id = await _connecter(emetteur, depot_refresh, uuid.uuid4())
    await depot_refresh.revoquer_famille(family_id, datetime.now(UTC))

    with pytest.raises(RefreshTokenRejoue):
        await use_case.executer(refresh_token)


async def test_un_refresh_de_jti_inconnu_leve_non_authentifie_sans_etre_un_rejeu(
    rafraichir_jetons: FixtureRafraichissement,
) -> None:
    # Structurellement valide (bien signé, non expiré) mais jamais persisté
    # (ex. base réinitialisée) : refusé, mais sans famille à révoquer donc
    # pas de `RefreshTokenRejoue` — juste l'échec générique.
    use_case, emetteur, _ = rafraichir_jetons
    jetons_orphelins = emetteur.emettre_jetons(uuid.uuid4())

    with pytest.raises(NonAuthentifie) as exc_info:
        await use_case.executer(jetons_orphelins.refresh_token)

    assert not isinstance(exc_info.value, RefreshTokenRejoue)
    assert exc_info.value.message == _MESSAGE_ECHEC_GENERIQUE


async def test_un_refresh_expire_leve_non_authentifie(
    rafraichir_jetons: FixtureRafraichissement,
) -> None:
    use_case, _, depot_refresh = rafraichir_jetons
    emetteur_expire = EmetteurJWT(
        cle_signature=CLE_SIGNATURE,
        duree_access=timedelta(minutes=15),
        duree_refresh=timedelta(days=-1),
    )
    refresh_token, _ = await _connecter(emetteur_expire, depot_refresh, uuid.uuid4())

    with pytest.raises(NonAuthentifie):
        await use_case.executer(refresh_token)


async def test_un_access_token_presente_comme_refresh_est_rejete(
    rafraichir_jetons: FixtureRafraichissement,
) -> None:
    # Un access token ne doit jamais être accepté par `/auth/refresh` : sans
    # ce contrôle du claim `type`, un access token (courte durée mais déjà
    # entre les mains d'un attaquant XSS) deviendrait un moyen détourné
    # d'obtenir un refresh token longue durée.
    use_case, emetteur, _ = rafraichir_jetons
    jetons = emetteur.emettre_jetons(uuid.uuid4())

    with pytest.raises(NonAuthentifie):
        await use_case.executer(jetons.access_token)


async def test_un_refresh_signe_avec_une_autre_cle_est_rejete(
    rafraichir_jetons: FixtureRafraichissement,
) -> None:
    use_case, _, _ = rafraichir_jetons
    emetteur_falsificateur = EmetteurJWT(
        cle_signature="une-autre-cle-tout-aussi-longue-32c",
        duree_access=timedelta(minutes=15),
        duree_refresh=timedelta(days=30),
    )
    jeton_falsifie = emetteur_falsificateur.emettre_jetons(uuid.uuid4()).refresh_token

    with pytest.raises(NonAuthentifie):
        await use_case.executer(jeton_falsifie)
