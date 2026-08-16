from modules.analyse.domaine.analyse import Analyse, StatutAnalyse
from modules.analyse.ports.cache import CachePort
from modules.analyse.ports.generateur_ia import GenerateurIAPort
from modules.analyse.ports.stockage_image import StockageImagePort


class ExecuterJobGeneration:
    """Corps du job de génération IA (F1, backlog.md — extrait de D3).

    Jusqu'à F1, cette logique vivait directement dans `GenererAnalyse.
    executer` (D3), appelée en synchrone. F1 la sépare en une classe à
    part pour que `GenererAnalyse` ne dépende plus que de `CachePort` et
    `FileJobsPort` : la génération elle-même (`GenerateurIAPort`,
    `StockageImagePort`) devient le détail d'exécution du job, invoqué par
    l'adaptateur `FileJobsPort` retenu — `FileJobsEnProcessusImmediat`
    l'appelle en synchrone dans ce même processus (dev) ; en prod, l'
    endpoint interne du worker (F3) l'appellera après réception d'une
    tâche Cloud Tasks (F2). Aucun des deux adaptateurs ne change une ligne
    de cette classe (agents.md §4).
    """

    def __init__(
        self,
        cache: CachePort,
        generateur_ia: GenerateurIAPort,
        stockage_image: StockageImagePort,
    ) -> None:
        self._cache = cache
        self._generateur_ia = generateur_ia
        self._stockage_image = stockage_image

    async def executer(self, analyse: Analyse) -> Analyse:
        try:
            resultat_texte = await self._generateur_ia.generer_texte(
                analyse.texte_source, analyse.source
            )
            image = await self._generateur_ia.generer_image(resultat_texte)
            resultat_image_url = await self._stockage_image.stocker(image, str(analyse.id))
        except Exception:
            # Sans ce filet, une exception pendant le job laisserait la
            # ligne bloquée en `pending` pour toujours : l'étape 4 de
            # l'algorithme (`GenererAnalyse`) renvoie 202 sans jamais
            # redéclencher de job tant que le statut reste `pending`.
            # `marquer_echec` complète le filet côté cache (agents.md §3 —
            # dégradation gracieuse ; E4 ajoute le circuit breaker en amont
            # de cet appel).
            await self._cache.marquer_echec(analyse)
            raise

        analyse_terminee = Analyse(
            id=analyse.id,
            texte_source=analyse.texte_source,
            source=analyse.source,
            statut=StatutAnalyse.DONE,
            created_at=analyse.created_at,
            resultat_texte=resultat_texte,
            resultat_image_url=resultat_image_url,
        )
        return await self._cache.marquer_termine(analyse_terminee)
