import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass
class EnregistrementRefresh:
    """État persisté d'un refresh token émis (C6, agents.md §4, §7).

    Un JWT refresh reste vérifiable de façon stateless (signature + `exp`,
    voir `EmetteurJetonPort.decoder_refresh`), mais la rotation avec
    détection de rejeu ne peut pas l'être : rien dans une signature ne prouve
    qu'un `jti` donné a déjà été échangé contre une nouvelle paire. Cet
    enregistrement est donc le pendant stateful minimal du refresh — zéro
    dépendance technique, comme `Utilisateur` (domaine/utilisateur.py).

    `family_id` est constant sur toute une chaîne de rotation (posé une
    seule fois, à la connexion) : c'est cet identifiant, pas le `jti`
    individuel, qui est révoqué en bloc quand un rejeu est détecté
    (`RafraichirJetons`, application/rafraichir_jetons.py).
    """

    jti: uuid.UUID
    family_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None = None
    revoked_at: datetime | None = None

    @property
    def est_valide(self) -> bool:
        """Faux si ce refresh a déjà été consommé par une rotation ou révoqué.

        Ne revérifie pas `expires_at` : le JWT porte déjà `exp` et est décodé
        (donc rejeté s'il est expiré) avant qu'un enregistrement ne soit
        même consulté — dupliquer ce contrôle ici serait une même
        connaissance à deux endroits (agents.md §1, DRY). `expires_at` sert
        uniquement à une purge/audit ultérieurs, pas à cette décision.
        """
        return self.used_at is None and self.revoked_at is None
