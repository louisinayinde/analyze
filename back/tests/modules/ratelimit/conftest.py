import time
from collections.abc import Callable

from modules.ratelimit.domaine.seau_jetons import EtatSeau, recharger_et_consommer
from modules.ratelimit.ports.rate_limiter import RateLimiterPort


class RateLimiterPortEnMémoire(RateLimiterPort):
    """Faux `RateLimiterPort` en mémoire, à réutiliser par les tests
    d'endpoints qui devront remplacer `LimiteurDebitPostgres` (G2/G3/G4)
    — même motif que `CachePortEnMémoire`
    (tests/modules/analyse/conftest.py) : isole les tests HTTP du réseau/DB
    (agents.md §6), sans jamais réimplémenter l'algorithme de recharge
    (réutilise `recharger_et_consommer`, agents.md §1 DRY).

    Horloge injectable (`horloge`, `time.monotonic` par défaut) pour que
    les tests contrôlent le temps écoulé sans `sleep` réel — même besoin
    que `CircuitBreaker` (modules/ia/adaptateurs/circuit_breaker.py),
    résolu ici par injection plutôt que monkeypatch d'un import module
    (plus simple : cette classe n'existe que dans les tests).
    """

    def __init__(self, horloge: Callable[[], float] = time.monotonic) -> None:
        self._horloge = horloge
        self._seaux: dict[str, EtatSeau] = {}

    async def consommer(self, cle: str, capacite: int, taux_recharge_par_seconde: float) -> bool:
        nouvel_etat, autorise = recharger_et_consommer(
            self._seaux.get(cle), capacite, taux_recharge_par_seconde, self._horloge()
        )
        self._seaux[cle] = nouvel_etat
        return autorise
