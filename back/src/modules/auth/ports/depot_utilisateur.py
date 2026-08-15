import uuid
from abc import ABC, abstractmethod
from datetime import datetime

from modules.auth.domaine.utilisateur import Utilisateur


class DépôtUtilisateurPort(ABC):
    """Port du domaine Auth vers la persistance (agents.md §4).

    Défini dans les termes du métier (créer, trouver, mettre à jour la
    dernière connexion), pas dans ceux de la techno : aucune mention de
    SQLAlchemy ou Postgres ici. L'adaptateur concret (C2,
    `DépôtUtilisateurPostgres`) implémente ce contrat ; le câblage
    port ↔ adaptateur se fait une seule fois, au point de composition
    (composition/registry.py), jamais dans le domaine ou l'application.

    Méthodes asynchrones car toute implémentation réaliste fait de l'I/O
    réseau vers la base (agents.md §3 : un appel qui sort du processus doit
    pouvoir être attendu sans bloquer le reste de l'API).
    """

    @abstractmethod
    async def creer(self, utilisateur: Utilisateur) -> Utilisateur:
        """Persiste un nouvel utilisateur et retourne l'entité persistée."""
        ...

    @abstractmethod
    async def trouver_par_email(self, email: str) -> Utilisateur | None:
        """Retourne l'utilisateur associé à cet email, ou `None` s'il n'existe pas.

        Ne lève pas d'exception sur l'absence de résultat : « utilisateur
        introuvable » est un cas nominal ici (ex. vérification de doublon
        à l'inscription), pas une erreur.
        """
        ...

    @abstractmethod
    async def mettre_a_jour_derniere_connexion(
        self, id_utilisateur: uuid.UUID, horodatage: datetime
    ) -> None:
        """Met à jour `last_login_at` pour l'utilisateur identifié par `id_utilisateur`."""
        ...
