from collections.abc import Awaitable, Callable

from modules.analyse.domaine.analyse import Analyse
from modules.analyse.ports.file_jobs import FileJobsPort


class FileJobsEnProcessusImmediat(FileJobsPort):
    """Implémentation dev de `FileJobsPort` (F1, backlog.md).

    Exécute le job en synchrone, dans le même processus que l'appelant :
    pas de Cloud Tasks à faire tourner en local (agents.md §2, budget —
    même esprit que `StockageImageFilesystem`/`GenerateurIAFactice`, qui
    évitent respectivement un bucket GCS et une clé LLM payante en dev).

    `executer_job` est injecté plutôt qu'une dépendance directe sur
    `ExecuterJobGeneration` : au point de composition (`composition/
    app.py`), cette fonction résout `CachePort`/`GenerateurIAPort`/
    `StockageImagePort` depuis le registre à chaque appel (même motif que
    `adaptateurs/api.py._generer_analyse`) — nécessaire pour que les tests
    qui remplacent ces adaptateurs par des doubles en mémoire *après* la
    construction de l'app restent pris en compte, puisque cet adaptateur
    `FileJobsPort` est câblé une seule fois, avant toute requête.
    """

    def __init__(self, executer_job: Callable[[Analyse], Awaitable[Analyse]]) -> None:
        self._executer_job = executer_job

    async def dispatcher(self, analyse: Analyse) -> None:
        # Propage toute exception du job à l'appelant (D3) : c'est ce qui
        # permet à `GenererAnalyse.executer` de laisser remonter un échec
        # de génération (E4 : circuit breaker -> `ServiceIndisponible`)
        # exactement comme avant F1, quand l'appel était fait en direct.
        await self._executer_job(analyse)
