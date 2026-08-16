import asyncio
import time
from collections.abc import Awaitable, Callable
from enum import Enum, auto
from typing import TypeVar

from shared.errors import ServiceIndisponible

T = TypeVar("T")

# E4 (backlog.md) : au-delà de ce nombre d'échecs consécutifs, le
# fournisseur est considéré en incident — on arrête d'essayer plutôt que de
# faire attendre chaque appelant le temps plein du timeout + retries (E3)
# pour un résultat prévisible (agents.md §3 : isoler la panne, pas la
# propager).
SEUIL_ECHECS_PAR_DEFAUT = 5

# Fenêtre pendant laquelle le circuit reste ouvert avant de retenter un
# appel de sonde (état semi-ouvert). Assez long pour ne pas remarteler un
# fournisseur en incident à chaque requête utilisateur, assez court pour
# qu'un incident transitoire se résorbe sans bloquer le produit des
# minutes durant.
DELAI_RECUPERATION_SECONDES_PAR_DEFAUT = 60.0


class _Etat(Enum):
    FERME = auto()  # fonctionnement normal, tous les appels passent
    OUVERT = auto()  # incident détecté, tous les appels échouent immédiatement
    SEMI_OUVERT = auto()  # délai de récupération écoulé, un appel de sonde est en cours


class CircuitBreaker:
    """Isole une panne de dépendance externe plutôt que de la propager
    (E4, backlog.md ; agents.md §3).

    Générique, sans dépendance à `GenerateurIAPort` ou à un fournisseur
    précis : ne connaît qu'« une fonction async qui peut échouer ». Câblé
    autour de `GenerateurIAPort.generer_texte` par
    `GenerateurIAAvecCircuitBreaker` (generateur_ia_avec_circuit_breaker.py),
    pas ici — ce module reste réutilisable pour tout autre appel externe
    qui demanderait la même protection (agents.md §1 : on factorise la
    même connaissance, pas la même forme).

    Machine à trois états :
    - FERMÉ : comportement normal, chaque appel passe et alimente le
      compteur d'échecs consécutifs.
    - OUVERT : dès que `seuil_echecs` échecs consécutifs sont atteints.
      Tout appel échoue immédiatement avec `ServiceIndisponible`, sans
      jamais toucher la fonction protégée — ça évite de marteler un
      fournisseur déjà en incident et fait gagner à l'appelant le temps
      plein d'un timeout (E3) pour un résultat prévisible.
    - SEMI-OUVERT : une fois `delai_recuperation_secondes` écoulé depuis
      l'ouverture, l'appel suivant est laissé passer comme sonde ; les
      autres continuent d'échouer immédiatement pendant ce temps (évite
      qu'un pic de requêtes concurrentes ne martèle toutes ensemble un
      fournisseur qui vient tout juste de tomber, ou n'est pas encore
      remonté). Succès de la sonde -> retour à FERMÉ, compteur remis à
      zéro. Échec -> retour à OUVERT, chronomètre relancé.

    État en mémoire du seul processus courant (pas de store externe type
    Redis) : cohérent avec le budget serré (agents.md §2) — un incident
    fournisseur touche tous les processus de la même façon, chacun détecte
    et isole la panne indépendamment, sans coordination nécessaire pour
    que la protection soit efficace. Si un futur worker séparé (F2,
    backlog.md) appelle aussi le fournisseur IA, il aura sa propre
    instance et son propre état — acceptable au vu de la taille (M) et du
    besoin réel de ce ticket.
    """

    def __init__(
        self,
        seuil_echecs: int = SEUIL_ECHECS_PAR_DEFAUT,
        delai_recuperation_secondes: float = DELAI_RECUPERATION_SECONDES_PAR_DEFAUT,
    ) -> None:
        self._seuil_echecs = seuil_echecs
        self._delai_recuperation_secondes = delai_recuperation_secondes
        self._etat = _Etat.FERME
        self._echecs_consecutifs = 0
        self._ouvert_depuis: float | None = None
        # Protège uniquement les transitions d'état, jamais l'appel à
        # `fonction` lui-même (voir `appeler`) : le tenir pendant l'appel
        # réseau sérialiserait tous les appels au fournisseur entre eux, ce
        # qui casserait la concurrence prouvée par D6 (agents.md §8).
        self._verrou = asyncio.Lock()

    async def appeler(self, fonction: Callable[[], Awaitable[T]]) -> T:
        """Exécute `fonction` au travers du circuit.

        Lève `ServiceIndisponible` sans jamais appeler `fonction` si le
        circuit est ouvert (ou déjà en train de sonder) — c'est ce message
        clair, mappé en 503 par `composition/app.py`, que reçoit
        l'utilisateur final à la place d'un timeout brut.
        """
        if not await self._laisser_passer():
            raise ServiceIndisponible()

        try:
            resultat = await fonction()
        except Exception:
            await self._enregistrer_echec()
            raise
        else:
            await self._enregistrer_succes()
            return resultat

    async def _laisser_passer(self) -> bool:
        async with self._verrou:
            if self._etat is _Etat.FERME:
                return True
            if self._etat is _Etat.OUVERT and self._recuperation_ecoulee():
                # Cet appelant précis devient la sonde ; tant que l'état
                # reste SEMI_OUVERT, les autres tombent dans `return False`.
                self._etat = _Etat.SEMI_OUVERT
                return True
            return False

    def _recuperation_ecoulee(self) -> bool:
        if self._ouvert_depuis is None:
            return False
        return time.monotonic() - self._ouvert_depuis >= self._delai_recuperation_secondes

    async def _enregistrer_echec(self) -> None:
        async with self._verrou:
            self._echecs_consecutifs += 1
            if self._etat is _Etat.SEMI_OUVERT or self._echecs_consecutifs >= self._seuil_echecs:
                self._etat = _Etat.OUVERT
                self._ouvert_depuis = time.monotonic()

    async def _enregistrer_succes(self) -> None:
        async with self._verrou:
            self._etat = _Etat.FERME
            self._echecs_consecutifs = 0
            self._ouvert_depuis = None
