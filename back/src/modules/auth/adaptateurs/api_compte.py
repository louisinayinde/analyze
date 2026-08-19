import logging
import uuid
from typing import cast

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict

from modules.auth.adaptateurs.api import UtilisateurReponse, get_current_user
from modules.auth.application.supprimer_compte import SupprimerCompte
from modules.auth.ports.depot_utilisateur import DépôtUtilisateurPort
from modules.auth.ports.hacheur_mot_de_passe import HacheurMotDePassePort
from shared.errors import NonAuthentifie
from shared.openapi import responses_erreur

# Adaptateur d'entrée distinct de `adaptateurs/api.py` (H3, agents.md §4) :
# `/compte` est une ressource (le compte de l'appelant), pas un flux d'auth
# (inscription/connexion/refresh/déconnexion) — même découpage que
# `api_worker.py` dans le module Analyse, un second routeur pour une
# préoccupation distincte au sein du même module.
router = APIRouter(prefix="/compte", tags=["compte"])

_logger = logging.getLogger("auth")


class SuppressionCompteRequete(BaseModel):
    """Redemande le mot de passe (vérification renforcée, H3, agents.md §7)."""

    model_config = ConfigDict(json_schema_extra={"example": {"mot_de_passe": "trombone-cheval-9"}})

    mot_de_passe: str


def _supprimer_compte(request: Request) -> SupprimerCompte:
    # Résolu à chaque requête : même motif que `_inscrire_utilisateur`
    # (modules/auth/adaptateurs/api.py) — les adaptateurs ne sont câblés
    # dans le registre qu'au lifespan de l'app (composition/app.py).
    registry = request.app.state.registry
    return SupprimerCompte(
        depot=registry.resolve(DépôtUtilisateurPort),
        hacheur=registry.resolve(HacheurMotDePassePort),
    )


def _depot_utilisateur(request: Request) -> DépôtUtilisateurPort:
    # `cast`, pas juste `return registry.resolve(...)` : même motif que
    # `_emetteur_jeton` (modules/auth/adaptateurs/api.py) — ici le port est
    # utilisé directement par la route, sans passer par un use-case dont le
    # constructeur typé infèrerait le retour à la place de mypy.
    return cast(DépôtUtilisateurPort, request.app.state.registry.resolve(DépôtUtilisateurPort))


@router.get(
    "",
    response_model=UtilisateurReponse,
    summary="Consulter son compte",
    response_description="Infos du compte de l'appelant authentifié.",
    responses=responses_erreur(
        (
            401,
            "non_authentifie",
            "Authentification requise.",
            "Aucun jeton présenté, jeton invalide/expiré, ou compte déjà supprimé.",
        ),
    ),
)
async def consulter_compte(
    depot: DépôtUtilisateurPort = Depends(_depot_utilisateur),
    user_id: uuid.UUID = Depends(get_current_user),
) -> UtilisateurReponse:
    # `user_id` vient exclusivement du JWT (`get_current_user`, C7), même
    # posture que `supprimer_compte` juste en dessous : impossible de
    # consulter le compte de quelqu'un d'autre depuis cette route.
    utilisateur = await depot.trouver_par_id(user_id)
    if utilisateur is None:
        # Cas limite (compte supprimé entre l'émission du JWT et cette
        # requête) : même exception que `SupprimerCompte.executer`
        # (application/supprimer_compte.py) — pas de canal distinct pour ce
        # cas plutôt qu'un jeton simplement expiré (agents.md §7).
        raise NonAuthentifie("Authentification requise.")
    return UtilisateurReponse.depuis_domaine(utilisateur)


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer son compte",
    response_description=(
        "Compte, refresh tokens et historique personnel supprimés "
        "(cascade au niveau du schéma, B6)."
    ),
    responses=responses_erreur(
        (
            401,
            "non_authentifie",
            "Mot de passe incorrect.",
            "Non authentifié, ou mot de passe incorrect (message générique, "
            "agents.md §7 — même posture que /auth/connexion).",
        ),
    ),
)
async def supprimer_compte(
    corps: SuppressionCompteRequete,
    use_case: SupprimerCompte = Depends(_supprimer_compte),
    user_id: uuid.UUID = Depends(get_current_user),
) -> None:
    # `user_id` vient exclusivement du JWT (`get_current_user`, C7), jamais
    # d'un paramètre de la requête (agents.md §7) : impossible de demander
    # la suppression du compte de quelqu'un d'autre depuis ce corps.
    await use_case.executer(user_id, corps.mot_de_passe)
    _logger.info("compte_supprime", extra={"user_id": str(user_id)})
