from abc import ABC, abstractmethod

from modules.analyse.domaine.analyse import Analyse


class FileJobsPort(ABC):
    """Port du domaine Analyse vers la file de jobs de génération (F1, agents.md §4).

    Défini dans les termes du métier (déclencher le job de génération pour
    une analyse), sans mention de Cloud Tasks ni de synchronisme —
    l'appelant (le use-case `GenererAnalyse`, D3) ignore complètement si le
    job s'exécute immédiatement ou plus tard, dans ce processus ou un
    autre. Deux adaptateurs (F1, backlog.md) : `FileJobsEnProcessusImmediat`
    (dev — exécute le job en synchrone dans le même processus, pas besoin
    de Cloud Tasks en local) et `FileJobsCloudTasks` (prod, activé
    seulement après L7 — provisionnement Terraform de la queue). Le
    câblage port -> adaptateur se fait au point de composition
    (`composition/app.py`), jamais dans le use-case (agents.md §4).

    `analyse` porte `texte_source` déjà nettoyé (D7) : c'est le seul
    endroit où ce texte est encore disponible pour l'adaptateur, `cache_
    resultat` ne persistant jamais le texte en clair (D2, `CachePort.
    obtenir_par_id`) — un adaptateur prod doit donc transporter ce texte
    lui-même dans le payload du job (ex. corps de la tâche Cloud Tasks),
    pas se contenter de l'id.

    Asynchrone (agents.md §3) : même un adaptateur qui « ne fait qu'
    enfiler » une tâche (Cloud Tasks) effectue un appel réseau.
    """

    @abstractmethod
    async def dispatcher(self, analyse: Analyse) -> None:
        """Déclenche le job de génération pour `analyse` (statut `pending`).

        Ne retourne rien : l'appelant (D3) ne doit jamais dépendre du
        résultat de la génération à cet endroit — il relit systématiquement
        l'état à jour via `CachePort.obtenir_par_id` après l'appel, ce qui
        fonctionne aussi bien si le job est déjà terminé (dev, synchrone)
        que s'il vient tout juste d'être enfilé (prod, encore `pending`).
        """
        ...
