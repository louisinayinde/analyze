import uuid
from abc import ABC, abstractmethod

from modules.analyse.domaine.entree_historique import EntreeHistorique


class DépôtHistoriquePort(ABC):
    """Port du domaine Analyse vers l'historique personnel (H3, agents.md §4).

    Défini dans les termes du métier (enregistrer, lister), pas dans ceux
    de la techno : aucune mention de SQLAlchemy/Postgres ici. Branché dans
    `GenererAnalyse` (D3/H3, cf. docstring de `HistoriqueModel`) : chaque
    soumission d'un utilisateur authentifié crée une ligne, que le texte
    soit un cache-hit ou un cache-miss — c'est un journal de ce que *cet*
    utilisateur a soumis, pas un ensemble dédupliqué de résultats.
    """

    @abstractmethod
    async def enregistrer(
        self, user_id: uuid.UUID, resultat_id: uuid.UUID, input_text: str
    ) -> None:
        """Ajoute une ligne d'historique pour `user_id`, pointant vers `resultat_id`
        (l'id du résultat partagé, `Analyse.id`), avec le texte tel que soumis.
        """
        ...

    @abstractmethod
    async def lister_par_utilisateur(
        self, user_id: uuid.UUID, page: int, page_size: int
    ) -> tuple[list[EntreeHistorique], int]:
        """Retourne une page de l'historique de `user_id`, triée du plus récent
        au plus ancien, ainsi que le nombre total de lignes (pour la
        pagination côté client).

        `user_id` est le seul filtre de scoping : l'appelant (le use-case,
        H3) le tient exclusivement du contexte authentifié, jamais d'un
        paramètre de requête (agents.md §7 — isolation multi-tenant).
        """
        ...
