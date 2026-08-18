import logging
import uuid

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict

from modules.auth.adaptateurs.api import get_current_user
from modules.auth.application.supprimer_compte import SupprimerCompte
from modules.auth.ports.depot_utilisateur import DépôtUtilisateurPort
from modules.auth.ports.hacheur_mot_de_passe import HacheurMotDePassePort
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
