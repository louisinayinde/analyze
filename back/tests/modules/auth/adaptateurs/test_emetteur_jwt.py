import uuid
from datetime import timedelta

import jwt
import pytest

from modules.auth.adaptateurs.emetteur_jwt import ALGORITHME, EmetteurJWT
from modules.auth.domaine.jeton import DonneesAcces, DonneesRefresh
from shared.errors import NonAuthentifie

CLE_SIGNATURE = "cle-de-test-suffisamment-longue-32c"


@pytest.fixture
def emetteur() -> EmetteurJWT:
    return EmetteurJWT(
        cle_signature=CLE_SIGNATURE,
        duree_access=timedelta(minutes=15),
        duree_refresh=timedelta(days=30),
    )


def test_emettre_jetons_produit_des_claims_minimaux_sans_pii(emetteur: EmetteurJWT) -> None:
    id_utilisateur = uuid.uuid4()

    jetons = emetteur.emettre_jetons(id_utilisateur)

    claims = jwt.decode(jetons.access_token, CLE_SIGNATURE, algorithms=[ALGORITHME])
    assert claims["sub"] == str(id_utilisateur)
    assert claims["type"] == "access"
    # Aucun claim en plus des 5 attendus : ni email, ni aucune autre PII
    # (agents.md §7 — claims minimaux, pas de PII dans le JWT).
    assert set(claims) == {"sub", "type", "iat", "exp", "jti"}


def test_emettre_jetons_distingue_access_et_refresh_par_claim_type(
    emetteur: EmetteurJWT,
) -> None:
    jetons = emetteur.emettre_jetons(uuid.uuid4())

    claims_refresh = jwt.decode(jetons.refresh_token, CLE_SIGNATURE, algorithms=[ALGORITHME])
    assert claims_refresh["type"] == "refresh"
    assert jetons.access_token != jetons.refresh_token


def test_emettre_jetons_signe_avec_lalgorithme_pinne(emetteur: EmetteurJWT) -> None:
    jetons = emetteur.emettre_jetons(uuid.uuid4())

    assert jwt.get_unverified_header(jetons.access_token)["alg"] == ALGORITHME


def test_un_jeton_alg_none_est_rejete_par_lallowlist(emetteur: EmetteurJWT) -> None:
    # Attaque "alg confusion" classique : un jeton non signé, prétendant
    # utiliser `alg: none`, ne doit jamais être accepté par un décodage qui
    # restreint explicitement les algorithmes (agents.md §7 — allowlist).
    jeton_falsifie = jwt.encode({"sub": "attaquant"}, key=None, algorithm="none")

    with pytest.raises(jwt.InvalidAlgorithmError):
        jwt.decode(jeton_falsifie, CLE_SIGNATURE, algorithms=[ALGORITHME])


def test_expires_in_correspond_a_la_duree_de_laccess_token(emetteur: EmetteurJWT) -> None:
    jetons = emetteur.emettre_jetons(uuid.uuid4())

    assert jetons.expires_in == 15 * 60
    assert jetons.token_type == "bearer"


def test_jetons_expose_le_jti_et_lexpiration_du_refresh_sans_le_redecoder(
    emetteur: EmetteurJWT,
) -> None:
    # C6 : le use-case (`ConnecterUtilisateur`, `RafraichirJetons`) doit
    # pouvoir persister `EnregistrementRefresh` sans jamais importer PyJWT
    # ni redécoder le jeton qu'il vient de recevoir (agents.md §1, DRY).
    jetons = emetteur.emettre_jetons(uuid.uuid4())

    claims_refresh = jwt.decode(jetons.refresh_token, CLE_SIGNATURE, algorithms=[ALGORITHME])
    assert str(jetons.refresh_jti) == claims_refresh["jti"]


def test_decoder_refresh_retourne_lidentite_dun_refresh_valide(emetteur: EmetteurJWT) -> None:
    id_utilisateur = uuid.uuid4()
    jetons = emetteur.emettre_jetons(id_utilisateur)

    donnees = emetteur.decoder_refresh(jetons.refresh_token)

    assert donnees == DonneesRefresh(user_id=id_utilisateur, jti=jetons.refresh_jti)


def test_decoder_refresh_rejette_un_access_token(emetteur: EmetteurJWT) -> None:
    # Un access token ne doit jamais être accepté comme refresh (C6) : sans
    # ce contrôle du claim `type`, un access token compromis (courte durée)
    # deviendrait un moyen détourné d'obtenir un refresh (longue durée).
    jetons = emetteur.emettre_jetons(uuid.uuid4())

    with pytest.raises(NonAuthentifie):
        emetteur.decoder_refresh(jetons.access_token)


def test_decoder_refresh_rejette_une_signature_invalide(emetteur: EmetteurJWT) -> None:
    jetons = emetteur.emettre_jetons(uuid.uuid4())
    autre_emetteur = EmetteurJWT(
        cle_signature="une-autre-cle-tout-aussi-longue-32c",
        duree_access=timedelta(minutes=15),
        duree_refresh=timedelta(days=30),
    )

    with pytest.raises(NonAuthentifie):
        autre_emetteur.decoder_refresh(jetons.refresh_token)


def test_decoder_refresh_rejette_un_refresh_expire() -> None:
    emetteur_expire = EmetteurJWT(
        cle_signature=CLE_SIGNATURE,
        duree_access=timedelta(minutes=15),
        duree_refresh=timedelta(days=-1),
    )
    jetons = emetteur_expire.emettre_jetons(uuid.uuid4())

    with pytest.raises(NonAuthentifie):
        emetteur_expire.decoder_refresh(jetons.refresh_token)


def test_decoder_refresh_rejette_un_jeton_alg_none(emetteur: EmetteurJWT) -> None:
    jeton_falsifie = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": "refresh", "jti": str(uuid.uuid4())},
        key=None,
        algorithm="none",
    )

    with pytest.raises(NonAuthentifie):
        emetteur.decoder_refresh(jeton_falsifie)


def test_decoder_acces_retourne_lidentite_dun_access_token_valide(emetteur: EmetteurJWT) -> None:
    id_utilisateur = uuid.uuid4()
    jetons = emetteur.emettre_jetons(id_utilisateur)

    donnees = emetteur.decoder_acces(jetons.access_token)

    assert donnees == DonneesAcces(user_id=id_utilisateur)


def test_decoder_acces_rejette_un_refresh_token(emetteur: EmetteurJWT) -> None:
    # Symétrique de `test_decoder_refresh_rejette_un_access_token` (C6) :
    # un refresh (longue durée) ne doit jamais être accepté comme access
    # token sur une route protégée (C7), sinon la distinction des deux
    # types de jetons n'a plus aucun effet de sécurité.
    jetons = emetteur.emettre_jetons(uuid.uuid4())

    with pytest.raises(NonAuthentifie):
        emetteur.decoder_acces(jetons.refresh_token)


def test_decoder_acces_rejette_une_signature_invalide(emetteur: EmetteurJWT) -> None:
    jetons = emetteur.emettre_jetons(uuid.uuid4())
    autre_emetteur = EmetteurJWT(
        cle_signature="une-autre-cle-tout-aussi-longue-32c",
        duree_access=timedelta(minutes=15),
        duree_refresh=timedelta(days=30),
    )

    with pytest.raises(NonAuthentifie):
        autre_emetteur.decoder_acces(jetons.access_token)


def test_decoder_acces_rejette_un_access_token_expire() -> None:
    emetteur_expire = EmetteurJWT(
        cle_signature=CLE_SIGNATURE,
        duree_access=timedelta(minutes=-1),
        duree_refresh=timedelta(days=30),
    )
    jetons = emetteur_expire.emettre_jetons(uuid.uuid4())

    with pytest.raises(NonAuthentifie):
        emetteur_expire.decoder_acces(jetons.access_token)


def test_decoder_acces_rejette_un_jeton_alg_none(emetteur: EmetteurJWT) -> None:
    jeton_falsifie = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": "access", "jti": str(uuid.uuid4())},
        key=None,
        algorithm="none",
    )

    with pytest.raises(NonAuthentifie):
        emetteur.decoder_acces(jeton_falsifie)
