import uuid

from modules.analyse.domaine.analyse import Analyse
from modules.analyse.ports.cache import CachePort
from shared.errors import RessourceIntrouvable


class ObtenirStatutAnalyse:
    """Use-case Analyse (D5, agents.md §4) — lecture du statut d'une analyse
    pour le polling client (`GET /analyses/{id}/statut`, projets.md §UX
    chemin cache-miss ; K3).

    Simple lecture au travers de `CachePort.obtenir_par_id` (D2) : contrairement
    à `GenererAnalyse` (D3), ce use-case ne transitionne jamais le statut
    d'une analyse — la route contourne `CachePort` directement sans passer
    par un use-case serait un smell (agents.md §6), d'où sa présence malgré
    sa taille minimale.
    """

    def __init__(self, cache: CachePort) -> None:
        self._cache = cache

    async def executer(self, analyse_id: uuid.UUID) -> Analyse:
        analyse = await self._cache.obtenir_par_id(analyse_id)
        if analyse is None:
            raise RessourceIntrouvable("Aucune analyse ne correspond à cet identifiant.")
        return analyse
