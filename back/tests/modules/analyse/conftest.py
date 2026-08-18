import uuid
from dataclasses import replace
from datetime import UTC, datetime

from modules.analyse.domaine.analyse import Analyse, StatutAnalyse
from modules.analyse.domaine.entree_historique import EntreeHistorique
from modules.analyse.ports.cache import CachePort
from modules.analyse.ports.historique import DépôtHistoriquePort
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

    async def obtenir_par_id(self, analyse_id: uuid.UUID) -> Analyse | None:
        for analyse in self._par_cle.values():
            if analyse.id == analyse_id:
                return analyse
        return None


class StockageImageEnMémoire(StockageImagePort):
    """Faux `StockageImagePort` en mémoire, partagé par les tests Analyse (D3).

    Les vrais adaptateurs (`StockageImageFilesystem`/`StockageImageGCS`,
    E5) ont leurs propres tests dédiés (tests/modules/analyse/adaptateurs/) ;
    ce faux permet de tester l'orchestration de `GenererAnalyse` sans
    écrire de vrais fichiers ni appeler GCS — le use-case ne connaît que le
    port (agents.md §4).
    """

    def __init__(self) -> None:
        self.contenus: dict[str, bytes] = {}

    async def stocker(self, contenu: bytes, cle: str) -> str:
        self.contenus[cle] = contenu
        return f"memoire://{cle}"


class DépôtHistoriqueEnMémoire(DépôtHistoriquePort):
    """Faux `DépôtHistoriquePort` en mémoire, partagé par les tests Analyse (H3).

    Isole `GenererAnalyse`/`ListerHistorique` du réseau/DB (agents.md §6) —
    même raisonnement que `CachePortEnMémoire` ci-dessus.
    """

    def __init__(self) -> None:
        self.entrees: list[EntreeHistorique] = []
        # `user_id` n'est pas porté par `EntreeHistorique` (agents.md §4 —
        # le domaine ne porte que ce dont l'appelant a besoin en retour) ;
        # ce faux dépôt le garde à part pour pouvoir filtrer dans
        # `lister_par_utilisateur`, comme le ferait une vraie clause `WHERE`.
        self._proprietaires: dict[uuid.UUID, uuid.UUID] = {}

    async def enregistrer(
        self, user_id: uuid.UUID, resultat_id: uuid.UUID, input_text: str
    ) -> None:
        entree = EntreeHistorique(
            id=uuid.uuid4(),
            resultat_id=resultat_id,
            input_text=input_text,
            created_at=datetime.now(UTC),
        )
        self.entrees.append(entree)
        self._proprietaires[entree.id] = user_id

    async def lister_par_utilisateur(
        self, user_id: uuid.UUID, page: int, page_size: int
    ) -> tuple[list[EntreeHistorique], int]:
        siennes = [e for e in self.entrees if self._proprietaires[e.id] == user_id]
        siennes.sort(key=lambda e: e.created_at, reverse=True)
        debut = (page - 1) * page_size
        return siennes[debut : debut + page_size], len(siennes)
