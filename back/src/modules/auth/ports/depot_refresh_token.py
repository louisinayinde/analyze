import uuid
from abc import ABC, abstractmethod
from datetime import datetime

from modules.auth.domaine.enregistrement_refresh import EnregistrementRefresh


class DépôtRefreshTokenPort(ABC):
    """Port du domaine Auth vers la persistance des refresh tokens (C6, agents.md §4, §7).

    Un JWT refresh reste vérifiable de façon stateless (signature + `exp`),
    mais la rotation avec détection de rejeu ne peut pas l'être : il faut
    savoir, côté serveur, si un `jti` donné a déjà été échangé contre une
    nouvelle paire ou révoqué, ce qu'aucune signature ne peut prouver à elle
    seule. Ce port est le pendant stateful minimal du refresh, défini dans
    les termes du métier — aucune mention de Postgres/SQLAlchemy ici.
    L'adaptateur concret (`DépôtRefreshTokenPostgres`) implémente ce
    contrat ; le câblage port -> adaptateur se fait une seule fois, au point
    de composition (composition/app.py), jamais dans le domaine ou
    l'application.

    Méthodes asynchrones car toute implémentation réaliste fait de l'I/O
    réseau vers la base (même raisonnement que `DépôtUtilisateurPort`).
    """

    @abstractmethod
    async def creer(self, enregistrement: EnregistrementRefresh) -> None:
        """Persiste un nouveau refresh token émis (à la connexion ou à une rotation)."""
        ...

    @abstractmethod
    async def trouver_par_jti(self, jti: uuid.UUID) -> EnregistrementRefresh | None:
        """Retourne l'enregistrement associé à ce jti, ou `None` s'il est inconnu.

        Ne lève pas d'exception sur l'absence de résultat : un `jti` inconnu
        est un cas nominal à gérer par l'appelant (refresh invalide,
        générique), pas une erreur technique.
        """
        ...

    @abstractmethod
    async def marquer_utilise(self, jti: uuid.UUID, horodatage: datetime) -> None:
        """Marque ce refresh token comme consommé par une rotation (chemin nominal)."""
        ...

    @abstractmethod
    async def revoquer_famille(self, family_id: uuid.UUID, horodatage: datetime) -> None:
        """Révoque tous les refresh tokens (utilisés ou non) de cette famille.

        Appelé uniquement sur détection de rejeu (C6) : un refresh déjà
        utilisé (ou déjà révoqué) qui est représenté signale que la famille
        entière est potentiellement compromise (vol du refresh token par un
        tiers) — toute la chaîne de rotation est donc invalidée d'un coup,
        pas seulement le jeton rejoué.
        """
        ...

    @abstractmethod
    async def revoquer(self, jti: uuid.UUID, horodatage: datetime) -> None:
        """Révoque ce seul refresh token (C7, déconnexion).

        Distinct de `revoquer_famille` : une déconnexion volontaire n'est
        pas un signal de compromission, seul le jeton présenté doit être
        invalidé — le reste de la famille (s'il y en avait un autre en vol,
        cas improbable mais pas traité ici) n'a pas à être touché.
        """
        ...
