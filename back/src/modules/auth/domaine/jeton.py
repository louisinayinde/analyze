import uuid
from dataclasses import dataclass
from datetime import datetime

from shared.errors import NonAuthentifie


@dataclass(frozen=True)
class Jetons:
    """Paire de jetons émise à la connexion ou à une rotation (C4, C6, agents.md §4).

    Entité du domaine Auth — zéro dépendance technique : ne connaît ni JWT
    ni PyJWT, seulement les deux jetons opaques (chaînes signées produites
    par l'adaptateur `EmetteurJWT`) et leur durée de vie. `expires_in` est
    exprimé en secondes, à l'usage du frontend (J3 — refresh silencieux
    avant expiration).

    `refresh_jti`/`refresh_expires_at` (C6) exposent les métadonnées du
    refresh token tout juste émis : sans elles, l'appelant (`ConnecterUtilisateur`,
    `RafraichirJetons`) devrait redécoder le JWT qu'il vient de recevoir pour
    savoir quoi persister dans `EnregistrementRefresh` — une même
    connaissance calculée deux fois (agents.md §1, DRY). Ces deux champs ne
    font volontairement pas partie de la réponse HTTP (`JetonsReponse`,
    adaptateurs/api.py) : usage interne au câblage port -> persistance, pas
    une information destinée au client.
    """

    access_token: str
    refresh_token: str
    expires_in: int
    refresh_jti: uuid.UUID
    refresh_expires_at: datetime
    token_type: str = "bearer"


@dataclass(frozen=True)
class DonneesRefresh:
    """Contenu utile d'un refresh token entrant, une fois vérifié (C6).

    Retourné par `EmetteurJetonPort.decoder_refresh` après que la signature,
    l'`alg` (allowlist), l'expiration et le claim `type` ont été validés :
    l'appelant (`RafraichirJetons`) n'a plus jamais à connaître PyJWT ni la
    forme des claims, seulement ces deux identifiants (agents.md §4).
    """

    user_id: uuid.UUID
    jti: uuid.UUID


@dataclass(frozen=True)
class DonneesAcces:
    """Contenu utile d'un access token entrant, une fois vérifié (C7).

    Retourné par `EmetteurJetonPort.decoder_acces` après que la signature,
    l'`alg` (allowlist) et le claim `type` ont été validés. Pas de `jti`
    ici, contrairement à `DonneesRefresh` : un access token est stateless
    par conception (courte durée, jamais persisté côté serveur — voir
    `shared/config.py`), donc rien à retrouver en base pour l'identifier.
    """

    user_id: uuid.UUID


class RefreshTokenRejoue(NonAuthentifie):
    """Un refresh déjà consommé (ou révoqué) est représenté : signal de vol (C6, agents.md §7).

    Sous-classe de `NonAuthentifie` : la réponse HTTP reste un 401 générique
    pour le client (pas d'oracle supplémentaire côté statut), mais un `code`
    distinct (`refresh_rejoue`) permet à `adaptateurs/api.py` de déclencher
    le log d'alerte dédié exigé par le ticket, séparément du log `INFO`
    générique des autres échecs de refresh (expiré, signature invalide...).
    `user_id`/`family_id` ne sont jamais sérialisés dans la réponse
    (`ErreurAPI` ne lit que `.code`/`.message`, cf. shared/errors.py) : ils
    ne servent qu'au log serveur, pour permettre l'investigation d'un vol de
    token.
    """

    code = "refresh_rejoue"
    message_par_defaut = "Session invalide, veuillez vous reconnecter."

    def __init__(self, user_id: uuid.UUID, family_id: uuid.UUID) -> None:
        super().__init__()
        self.user_id = user_id
        self.family_id = family_id
