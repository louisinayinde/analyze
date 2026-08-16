import uuid
from datetime import UTC, datetime

from modules.analyse.domaine.analyse import Analyse, SourceAnalyse, StatutAnalyse
from modules.analyse.ports.cache import CachePort
from modules.analyse.ports.generateur_ia import GenerateurIAPort
from modules.analyse.ports.stockage_image import StockageImagePort


class GenererAnalyse:
    """Use-case Analyse (D3, agents.md §4) — logique de concurrence du cache exact.

    Implémente exactement l'algorithme de projets.md (§Concurrence sur le
    cache) : deux users qui collent le même texte en même temps ne doivent
    déclencher qu'un seul appel IA, sinon la promesse de cache exact du
    projet est cassée (backlog.md D3 — ticket bloquant agents.md §6 🔴).

    Ne dépend que des ports (`CachePort`, `GenerateurIAPort`,
    `StockageImagePort`), jamais d'un adaptateur concret : brancher
    l'adaptateur IA réel (E1/E2) ou le stockage réel (E5) derrière ces
    mêmes ports ne doit toucher aucune ligne de ce fichier (agents.md §4).
    L'appel au job de génération est fait ici en synchrone, direct — le
    port `FileJobsPort` (F1) le rendra asynchrone sans changer cette
    logique de concurrence.
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

    async def executer(self, texte_source: str, source: SourceAnalyse) -> Analyse:
        candidate = Analyse(
            id=uuid.uuid4(),
            texte_source=texte_source,
            source=source,
            statut=StatutAnalyse.PENDING,
            created_at=datetime.now(UTC),
        )

        # Étape 1 : `INSERT ... ON CONFLICT (input_hash) DO NOTHING` côté
        # adaptateur (D2) — sous deux appels concurrents sur le même texte,
        # Postgres ne laisse `cree=True` qu'à un seul appelant.
        analyse, cree = await self._cache.inserer_si_absent(candidate)

        if cree:
            # Étape 2 : on est le premier appelant pour ce texte + cette
            # source, on déclenche le job.
            return await self._generer_et_persister(analyse)

        if analyse.statut is StatutAnalyse.DONE:
            # Étape 3 : résultat déjà en cache, aucun nouvel appel IA.
            await self._cache.incrementer_hit_count(analyse)
            return analyse

        # Étape 4 : la ligne existe déjà en `pending` (un autre appelant
        # génère déjà le résultat) — ou en `failed` (hors du périmètre de
        # retry de ce ticket, voir E4). Dans les deux cas, pas de nouvel
        # appel IA : l'appelant renvoie 202 et laisse le client poller.
        return analyse

    async def _generer_et_persister(self, analyse: Analyse) -> Analyse:
        try:
            resultat_texte = await self._generateur_ia.generer_texte(
                analyse.texte_source, analyse.source
            )
            image = await self._generateur_ia.generer_image(resultat_texte)
            resultat_image_url = await self._stockage_image.stocker(image, str(analyse.id))
        except Exception:
            # Sans ce filet, une exception pendant le job laisserait la
            # ligne bloquée en `pending` pour toujours : l'étape 4 de
            # l'algorithme renvoie 202 sans jamais redéclencher de job tant
            # que le statut reste `pending`. `marquer_echec` complète le
            # filet côté cache (agents.md §3 — dégradation gracieuse ; E4
            # ajoutera le circuit breaker en amont de cet appel).
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
