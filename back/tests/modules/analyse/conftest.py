import uuid
from dataclasses import replace

from modules.analyse.domaine.analyse import Analyse, StatutAnalyse
from modules.analyse.ports.cache import CachePort
from modules.analyse.ports.stockage_image import StockageImagePort


class CachePortEnMémoire(CachePort):
    """Faux `CachePort` en mémoire, partagé par les tests Analyse (D3).

    Reproduit la sémantique de `INSERT ... ON CONFLICT (input_hash) DO
    NOTHING` (projets.md §Concurrence sur le cache) via une clé de dict
    (texte_source, source) plutôt qu'un hash — le port raisonne déjà en
    ces termes (agents.md §4), le calcul du hash restant un détail de
    l'adaptateur Postgres réel (D2). Isole le use-case D3 du réseau/DB
    (agents.md §6).
    """

    def __init__(self) -> None:
        self._par_cle: dict[tuple[str, str], Analyse] = {}
        self.hit_counts: dict[uuid.UUID, int] = {}

    def _cle(self, analyse: Analyse) -> tuple[str, str]:
        return (analyse.texte_source, analyse.source.value)

    async def inserer_si_absent(self, analyse: Analyse) -> tuple[Analyse, bool]:
        cle = self._cle(analyse)
        existante = self._par_cle.get(cle)
        if existante is not None:
            return existante, False
        self._par_cle[cle] = analyse
        return analyse, True

    async def marquer_termine(self, analyse: Analyse) -> Analyse:
        terminee = replace(analyse, statut=StatutAnalyse.DONE)
        self._par_cle[self._cle(analyse)] = terminee
        return terminee

    async def marquer_echec(self, analyse: Analyse) -> None:
        self._par_cle[self._cle(analyse)] = replace(analyse, statut=StatutAnalyse.FAILED)

    async def incrementer_hit_count(self, analyse: Analyse) -> None:
        self.hit_counts[analyse.id] = self.hit_counts.get(analyse.id, 0) + 1


class StockageImageEnMémoire(StockageImagePort):
    """Faux `StockageImagePort` en mémoire, partagé par les tests Analyse (D3).

    Le vrai adaptateur (filesystem local / GCS) arrive en E5 ; ce faux
    permet de tester l'orchestration de `GenererAnalyse` sans dépendre de
    son existence — le use-case ne connaît que le port (agents.md §4).
    """

    def __init__(self) -> None:
        self.contenus: dict[str, bytes] = {}

    async def stocker(self, contenu: bytes, cle: str) -> str:
        self.contenus[cle] = contenu
        return f"memoire://{cle}"
