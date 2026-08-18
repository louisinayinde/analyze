import logging
import uuid
from datetime import UTC, datetime
from typing import cast

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth import exceptions as google_auth_exceptions
from google.auth.transport import requests as google_auth_requests
from google.oauth2 import id_token
from pydantic import BaseModel

from modules.analyse.application.executer_job_generation import ExecuterJobGeneration
from modules.analyse.domaine.analyse import Analyse, SourceAnalyse, StatutAnalyse
from modules.analyse.ports.cache import CachePort
from modules.analyse.ports.generateur_ia import GenerateurIAPort
from modules.analyse.ports.stockage_image import StockageImagePort
from shared.config import Settings
from shared.errors import AccesRefuse

# Adaptateur d'entrée (driving adapter, agents.md §4), distinct de
# `adaptateurs/api.py` : celui-ci ne reçoit jamais de requête navigateur,
# seulement des tâches HTTP émises par Cloud Tasks (F1,
# `FileJobsCloudTasks._creer_tache`), donc jamais monté sur `api`
# (composition/app.py) — seulement sur `worker` (composition/worker.py,
# F3, backlog.md).
router_interne = APIRouter(prefix="/internal/jobs", tags=["worker"])

# `auto_error=False` : sans jeton présenté, on lève nous-mêmes `AccesRefuse`
# pour rester dans l'enveloppe d'erreur unique de l'API (`ErreurAPI`)
# plutôt que de laisser FastAPI renvoyer son 403 générique non formatté —
# même motif que `modules/auth/adaptateurs/api.py._bearer_scheme`.
_bearer_scheme = HTTPBearer(auto_error=False)

# Réutilisé entre requêtes : `google.auth.transport.requests.Request` met
# en cache les certificats publics Google (renouvelés rarement, cf.
# docstring de `google.oauth2.id_token`) — une instance par requête HTTP
# entrante referait cet appel réseau à chaque tâche reçue pour rien
# (agents.md §2, §8).
_transport = google_auth_requests.Request()

_logger = logging.getLogger("worker")


class TacheAnalyseRequete(BaseModel):
    """Forme du corps posté par `FileJobsCloudTasks._creer_tache` (F1).

    Porte `texte_source` en clair : `cache_resultat` ne le persiste jamais
    (D2), ce corps de requête est donc le seul endroit où ce processus peut
    encore le récupérer pour exécuter la génération.
    """

    analyse_id: uuid.UUID
    texte_source: str
    source: SourceAnalyse


def _settings(request: Request) -> Settings:
    # `cast`, pas juste `return request.app.state.settings` : `app.state`
    # est dynamiquement typé (`Any`) côté Starlette — même idiome que
    # `modules/auth/adaptateurs/api.py._emetteur_jeton`.
    return cast(Settings, request.app.state.settings)


async def verifier_origine_cloud_tasks(
    identifiants: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(_settings),
) -> None:
    """Vérifie que l'appel provient bien de Cloud Tasks, avec le service
    account attendu (F3, backlog.md ; agents.md §7 — sécurité non
    négociable même sur un endpoint interne).

    On ne réinvente pas de vérification JWT maison (agents.md §7) :
    `google.oauth2.id_token.verify_oauth2_token` est la primitive standard
    du SDK Google — elle télécharge les certificats publics Google, vérifie
    la signature, l'expiration et l'`audience` du jeton OIDC joint par
    Cloud Tasks (`tasks_v2.OidcToken`, F1). On vérifie en plus que l'email
    du compte de service signataire correspond exactement à celui attendu
    (`settings.worker_service_account_email`) : un jeton Google par ailleurs
    valide, mais signé par un *autre* compte de service, ne doit pas passer
    — sans cette étape, n'importe quel service GCP capable d'obtenir un
    jeton OIDC Google pourrait appeler cet endpoint.

    Toute cause d'échec (jeton absent, expiré, mal signé, mauvaise
    audience, mauvais compte de service) retombe sur la même exception,
    sans distinction exposée au client (agents.md §7 — même posture que
    `modules/auth/adaptateurs/api.py.get_current_user`) ; la cause précise
    reste en log côté serveur pour l'investigation.
    """
    if identifiants is None:
        _logger.warning("jeton_oidc_absent")
        raise AccesRefuse("Jeton OIDC requis.")

    try:
        claims = id_token.verify_oauth2_token(
            identifiants.credentials, _transport, audience=settings.worker_internal_url
        )
    except google_auth_exceptions.GoogleAuthError as exc:
        _logger.warning("jeton_oidc_invalide", extra={"raison": str(exc)})
        raise AccesRefuse("Jeton OIDC invalide.") from exc

    if claims.get("email") != settings.worker_service_account_email or not claims.get(
        "email_verified"
    ):
        _logger.warning(
            "jeton_oidc_compte_de_service_inattendu", extra={"email": claims.get("email")}
        )
        raise AccesRefuse("Jeton OIDC non autorisé pour cet endpoint.")


def _executer_job_generation(request: Request) -> ExecuterJobGeneration:
    # Résolu à chaque requête, comme `_generer_analyse`
    # (modules/analyse/adaptateurs/api.py) : les adaptateurs ne sont câblés
    # dans le registre qu'au lifespan de l'app worker (composition/worker.py).
    registry = request.app.state.registry
    return ExecuterJobGeneration(
        cache=registry.resolve(CachePort),
        generateur_ia=registry.resolve(GenerateurIAPort),
        stockage_image=registry.resolve(StockageImagePort),
    )


@router_interne.post(
    "/analyses",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(verifier_origine_cloud_tasks)],
)
async def recevoir_tache_analyse(
    corps: TacheAnalyseRequete,
    use_case: ExecuterJobGeneration = Depends(_executer_job_generation),
) -> None:
    """Reçoit une tâche Cloud Tasks et exécute le job de génération (F3).

    Équivalent, côté transport HTTP/Cloud Tasks, de ce que
    `FileJobsEnProcessusImmediat.dispatcher` fait déjà en direct côté dev :
    reconstruire l'`Analyse` (statut `pending`, ce processus ne relit
    jamais la ligne de cache avant d'exécuter le job) et appeler
    `ExecuterJobGeneration.executer` (F1). `created_at` n'a pas besoin
    d'être fidèle à l'originale : `marquer_termine`/`marquer_echec` (D2)
    mettent à jour la ligne existante par `id`, sans jamais lire ce champ.

    Pas de try/except ici : si le job échoue, `ExecuterJobGeneration`
    marque déjà la ligne `failed` (filet de sécurité, F1) puis laisse
    l'exception remonter — `configure_error_handling` la traduit en 5xx,
    ce qui fait retenter la tâche par Cloud Tasks selon la politique de
    retry de la queue (agents.md §3, retries avec backoff), sans code
    supplémentaire ici.
    """
    analyse = Analyse(
        id=corps.analyse_id,
        texte_source=corps.texte_source,
        source=corps.source,
        statut=StatutAnalyse.PENDING,
        created_at=datetime.now(UTC),
    )
    _logger.info("job_recu", extra={"analyse_id": str(corps.analyse_id)})
    await use_case.executer(analyse)
