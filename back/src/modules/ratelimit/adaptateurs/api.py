import logging
import uuid
from typing import cast

from fastapi import Depends, Request

from modules.auth.index import get_current_user_optional
from modules.ratelimit.ports.rate_limiter import RateLimiterPort
from shared.config import Settings
from shared.errors import LimiteDebitDepassee

# Adaptateur d'entrée (driving adapter, agents.md §4) : seul fichier du
# module Ratelimit qui connaît FastAPI. Traduit HTTP -> `RateLimiterPort`
# (G1), lui-même ignorant de HTTP — même découpage que
# `modules/auth/adaptateurs/api.py` (`get_current_user`) et
# `modules/analyse/adaptateurs/api_worker.py` (`verifier_origine_cloud_tasks`).
# Câblé au point de composition via `index.py` (G2, backlog.md).

_logger = logging.getLogger("ratelimit")


def _rate_limiter(request: Request) -> RateLimiterPort:
    # `cast`, pas juste `return request.app.state.registry.resolve(...)` :
    # même idiome que `modules/auth/adaptateurs/api.py._emetteur_jeton`
    # (`app.state` est dynamiquement typé côté Starlette).
    return cast(RateLimiterPort, request.app.state.registry.resolve(RateLimiterPort))


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def _adresse_ip_appelante(request: Request) -> str:
    """Retourne l'IP à utiliser comme clé de seau pour un appelant anonyme.

    Priorité à `X-Forwarded-For` (posé par l'infrastructure devant l'API en
    prod, ex. Cloud Run/GCLB — non encore provisionné, voir backlog.md
    §EPIC L) : `request.client.host` y vaudrait l'IP du proxy amont, pas
    celle du client réel, ce qui ferait retomber tout le trafic sur une
    seule clé de seau (sous-protection totale, pas juste imprécise). Ne
    retient que le premier maillon de la liste — la partie posée par
    l'infrastructure de confiance, jamais une valeur que le client aurait
    pu falsifier en s'ajoutant lui-même en tête.

    Ce en-tête reste falsifiable par un client qui parle directement au
    conteneur (dev local, ou prod tant qu'aucune passerelle de confiance ne
    filtre les en-têtes entrants) : ce n'est pas un défaut de ce middleware
    mais la raison pour laquelle G (rate limiting applicatif) est
    explicitement documenté comme un complément à un WAF/rate limiting de
    périphérie (backlog.md §EPIC L), pas la seule ligne de défense
    (agents.md §7 — défense en profondeur).
    """
    en_tete = request.headers.get("x-forwarded-for")
    if en_tete:
        return en_tete.split(",")[0].strip()
    return request.client.host if request.client is not None else "inconnue"


async def limiter_debit_ip_anonyme(
    request: Request,
    limiteur: RateLimiterPort = Depends(_rate_limiter),
    settings: Settings = Depends(_settings),
    user_id: uuid.UUID | None = Depends(get_current_user_optional),
) -> None:
    """Dépendance FastAPI qui applique le quota par IP aux appelants
    anonymes de `POST /analyses` (G2, backlog.md).

    Ne s'applique qu'en l'absence d'utilisateur authentifié : un appelant
    connecté aura son propre quota par `user_id`, généralement plus
    généreux (G3, pas encore câblé) — jusque-là, un appel authentifié n'est
    tout simplement pas limité par ce middleware, plutôt que de partager à
    tort le quota IP plus restrictif pensé pour l'anonyme (Single
    Responsibility, agents.md §1 : ce middleware ne fait qu'une politique,
    l'anonyme ; G3 apportera la sienne sans toucher à celle-ci).

    Réutilise `get_current_user_optional` (déjà résolu par la route
    elle-même, `modules/analyse/adaptateurs/api.py`) : FastAPI met en cache
    le résultat d'une dépendance par requête, donc le jeton n'est décodé
    qu'une seule fois (agents.md §1, DRY) — jamais une seconde
    vérification divergente.

    Lève `LimiteDebitDepassee` (429) si le seau IP est vide ; ne renvoie
    rien sinon, la requête continue normalement vers le use-case.
    """
    if user_id is not None:
        return

    cle = f"ip:{_adresse_ip_appelante(request)}"
    autorise = await limiteur.consommer(
        cle,
        capacite=settings.rate_limit_analyses_ip_capacite,
        taux_recharge_par_seconde=settings.rate_limit_analyses_ip_taux_par_minute / 60,
    )
    if not autorise:
        _logger.warning("limite_debit_ip_depassee")
        raise LimiteDebitDepassee()
