from abc import ABC, abstractmethod

from modules.analyse.domaine.analyse import Analyse


class CachePort(ABC):
    """Port du domaine Analyse vers le cache exact partagé (D1, agents.md §4).

    Porte le contrat de l'algorithme de concurrence (projets.md
    §Concurrence sur le cache), implémenté par l'adaptateur Postgres en D2
    et orchestré par le use-case `GenererAnalyse` en D3 :
    1. `inserer_si_absent` — équivalent métier d'un
       `INSERT ... ON CONFLICT (input_hash) DO NOTHING`.
    2. Ligne déjà `done` → le use-case renvoie directement le résultat.
    3. Ligne déjà `pending` → le use-case renvoie `202`, sans nouvel appel
       IA.
    4. `marquer_termine` / `marquer_echec` — transition de la ligne une
       fois le job de génération terminé.

    Le calcul de la clé de cache (`input_hash` = hash du texte normalisé +
    source) est un détail d'implémentation de l'adaptateur (D2) : le port
    raisonne en termes de texte + source, jamais de hash — c'est la
    définition même d'un port « dans les termes du métier » (agents.md §4).
    """

    @abstractmethod
    async def inserer_si_absent(self, analyse: Analyse) -> tuple[Analyse, bool]:
        """Tente de créer l'entrée de cache pour `analyse.texte_source` +
        `analyse.source`.

        `analyse` est construite par l'appelant (D3) avec un nouvel `id` et
        `statut = StatutAnalyse.PENDING` ; l'adaptateur décide, à partir du
        texte et de la source, s'il s'agit d'une ligne nouvelle ou d'une
        ligne déjà existante (pending, done ou failed).

        Retourne `(analyse_persistee, cree)` où `cree` indique si cet appel
        est celui qui a créé la ligne (on est le premier appelant, donc
        celui qui doit déclencher le job de génération) ou si une ligne
        existait déjà pour ce texte + cette source.
        """
        ...

    @abstractmethod
    async def marquer_termine(self, analyse: Analyse) -> Analyse:
        """Persiste `analyse` en `statut = StatutAnalyse.DONE`, avec
        `resultat_texte` et `resultat_image_url` renseignés.
        """
        ...

    @abstractmethod
    async def marquer_echec(self, analyse: Analyse) -> None:
        """Persiste `analyse` en `statut = StatutAnalyse.FAILED`.

        Ne laisse jamais une ligne bloquée en `pending` après l'échec d'un
        job (agents.md §3 — dégradation gracieuse, complété en E4).
        """
        ...

    @abstractmethod
    async def incrementer_hit_count(self, analyse: Analyse) -> None:
        """Incrémente le compteur de cache-hit de la ligne partagée.

        Métrique directe de l'économie de cache (projets.md
        §Observabilité) — appelée à chaque fois qu'une requête trouve une
        ligne déjà `done`, jamais lors de la création initiale.
        """
        ...
