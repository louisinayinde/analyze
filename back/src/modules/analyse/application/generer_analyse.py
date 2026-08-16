import uuid
from datetime import UTC, datetime

from modules.analyse.domaine.analyse import Analyse, SourceAnalyse, StatutAnalyse
from modules.analyse.domaine.texte_analyse import valider_et_nettoyer_texte
from modules.analyse.ports.cache import CachePort
from modules.analyse.ports.file_jobs import FileJobsPort


class GenererAnalyse:
    """Use-case Analyse (D3, agents.md §4) — logique de concurrence du cache exact.

    Implémente exactement l'algorithme de projets.md (§Concurrence sur le
    cache) : deux users qui collent le même texte en même temps ne doivent
    déclencher qu'un seul appel IA, sinon la promesse de cache exact du
    projet est cassée (backlog.md D3 — ticket bloquant agents.md §6 🔴).
    1. `INSERT ... ON CONFLICT (input_hash) DO NOTHING` avec
       `status = 'pending'` (`CachePort.inserer_si_absent`).
    2. Insertion réussie → on est le premier, on déclenche le job via
       `FileJobsPort` (F1, backlog.md).
    3. Ligne déjà `done` → retour direct du résultat.
    4. Ligne déjà `pending` → retour tel quel, pas de nouvel appel.

    Ne dépend que des ports (`CachePort`, `FileJobsPort`), jamais d'un
    adaptateur concret : remplacer `FileJobsEnProcessusImmediat` (dev) par
    `FileJobsCloudTasks` (prod, F1) — ou, en amont, l'adaptateur IA réel
    (E1/E2) par le stockage réel (E5) derrière `ExecuterJobGeneration` —
    ne touche aucune ligne de ce fichier (agents.md §4).

    F1 a extrait la génération elle-même (appel IA + stockage image) dans
    `ExecuterJobGeneration` : ce use-case ne fait plus que l'orchestration
    du cache et le déclenchement du job, jamais la génération en direct
    (c'est tout l'objet du port `FileJobsPort` — avant F1, l'appel était
    fait ici en synchrone, direct, en attendant que ce ticket existe).
    """

    def __init__(self, cache: CachePort, file_jobs: FileJobsPort) -> None:
        self._cache = cache
        self._file_jobs = file_jobs

    async def executer(self, texte_source: str, source: SourceAnalyse) -> Analyse:
        # D7 (backlog.md) : longueur, vide/whitespace et sanitisation
        # anti prompt-injection grossière, appliquées ici pour couvrir tout
        # appelant du use-case, pas seulement `POST /analyses` (D4).
        texte_source = valider_et_nettoyer_texte(texte_source)

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
            # source, on déclenche le job via le port (F1) plutôt que
            # d'appeler la génération en direct.
            await self._file_jobs.dispatcher(analyse)
            # `dispatcher` ne retourne rien (le use-case ne doit pas
            # dépendre du résultat de la génération à cet endroit) : on
            # relit systématiquement l'état à jour. `FileJobsEnProcessusImmediat`
            # (dev) exécute le job en synchrone avant de retourner — la
            # relecture voit donc déjà `done`/`failed`. `FileJobsCloudTasks`
            # (prod) retourne dès l'enfilage de la tâche — la relecture voit
            # encore `pending`, ce qui est le `202` attendu pour un
            # cache-miss réellement asynchrone.
            return await self._cache.obtenir_par_id(analyse.id) or analyse

        if analyse.statut is StatutAnalyse.DONE:
            # Étape 3 : résultat déjà en cache, aucun nouvel appel IA.
            await self._cache.incrementer_hit_count(analyse)
            return analyse

        # Étape 4 : la ligne existe déjà en `pending` (un autre appelant a
        # déjà déclenché le job) — ou en `failed` (hors du périmètre de
        # retry de ce ticket, voir E4). Dans les deux cas, pas de nouveau
        # dispatch : l'appelant renvoie 202 et laisse le client poller.
        return analyse
