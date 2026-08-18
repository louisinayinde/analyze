import uuid

from modules.analyse.domaine.entree_historique import EntreeHistorique
from modules.analyse.ports.historique import DépôtHistoriquePort


class ListerHistorique:
    """Use-case Analyse (H3, agents.md §4, §6).

    Orchestration fine mais volontaire : passer par un use-case plutôt que
    d'appeler `DépôtHistoriquePort` directement depuis la route évite le
    smell architectural pointé par agents.md §6 (contourner le use-case
    depuis un contrôleur), et donne un point d'extension unique si une
    règle métier s'ajoute un jour (ex. filtrage, agrégation) sans toucher
    à la route ni à l'adaptateur.
    """

    def __init__(self, depot: DépôtHistoriquePort) -> None:
        self._depot = depot

    async def executer(
        self, user_id: uuid.UUID, page: int, page_size: int
    ) -> tuple[list[EntreeHistorique], int]:
        return await self._depot.lister_par_utilisateur(user_id, page, page_size)
