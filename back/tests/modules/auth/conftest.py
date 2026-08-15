import uuid
from datetime import datetime

from modules.auth.domaine.enregistrement_refresh import EnregistrementRefresh
from modules.auth.domaine.utilisateur import Utilisateur
from modules.auth.ports.depot_refresh_token import DépôtRefreshTokenPort
from modules.auth.ports.depot_utilisateur import DépôtUtilisateurPort
from shared.errors import ConflitRessource


class DépôtUtilisateurEnMémoire(DépôtUtilisateurPort):
    """Faux dépôt en mémoire, partagé par les tests Auth (C3, C4).

    Isole les use-cases du réseau/DB (agents.md §6). Une seule
    implémentation de ce faux dépôt pour tous les tests du module : le
    comportement d'un dépôt en mémoire (créer, trouver, mettre à jour la
    dernière connexion) est la même connaissance quel que soit le use-case
    qui l'exerce — le dupliquer par fichier de test irait contre le DRY
    d'agents.md §1.
    """

    def __init__(self) -> None:
        self._par_email: dict[str, Utilisateur] = {}
        self.dernieres_connexions: dict[uuid.UUID, datetime] = {}

    async def creer(self, utilisateur: Utilisateur) -> Utilisateur:
        if utilisateur.email in self._par_email:
            # Même message que l'adaptateur Postgres réel (C2) : c'est
            # justement ce que le use-case d'inscription (C3) doit
            # intercepter et remplacer par un message générique côté API.
            raise ConflitRessource("Un compte existe déjà avec cet email.")
        self._par_email[utilisateur.email] = utilisateur
        return utilisateur

    async def trouver_par_email(self, email: str) -> Utilisateur | None:
        return self._par_email.get(email)

    async def mettre_a_jour_derniere_connexion(
        self, id_utilisateur: uuid.UUID, horodatage: datetime
    ) -> None:
        self.dernieres_connexions[id_utilisateur] = horodatage


class DépôtRefreshTokenEnMémoire(DépôtRefreshTokenPort):
    """Faux dépôt en mémoire, partagé par les tests Auth (C6).

    Même raisonnement que `DépôtUtilisateurEnMémoire` ci-dessus : une seule
    implémentation du comportement d'un dépôt refresh en mémoire pour tous
    les tests qui l'exercent (use-case, API) — le dupliquer par fichier de
    test irait contre le DRY d'agents.md §1.
    """

    def __init__(self) -> None:
        self._par_jti: dict[uuid.UUID, EnregistrementRefresh] = {}

    async def creer(self, enregistrement: EnregistrementRefresh) -> None:
        self._par_jti[enregistrement.jti] = enregistrement

    async def trouver_par_jti(self, jti: uuid.UUID) -> EnregistrementRefresh | None:
        return self._par_jti.get(jti)

    async def marquer_utilise(self, jti: uuid.UUID, horodatage: datetime) -> None:
        enregistrement = self._par_jti[jti]
        enregistrement.used_at = horodatage

    async def revoquer_famille(self, family_id: uuid.UUID, horodatage: datetime) -> None:
        for enregistrement in self._par_jti.values():
            if enregistrement.family_id == family_id and enregistrement.revoked_at is None:
                enregistrement.revoked_at = horodatage

    async def revoquer(self, jti: uuid.UUID, horodatage: datetime) -> None:
        enregistrement = self._par_jti.get(jti)
        if enregistrement is not None and enregistrement.revoked_at is None:
            enregistrement.revoked_at = horodatage
