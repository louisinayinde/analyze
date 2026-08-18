import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict

from modules.analyse.application.lister_historique import ListerHistorique
from modules.analyse.domaine.entree_historique import EntreeHistorique
from modules.analyse.ports.historique import DépôtHistoriquePort
from modules.auth.index import get_current_user
from shared.openapi import responses_erreur

# Adaptateur d'entrée distinct de `adaptateurs/api.py` (H3, agents.md §4) :
# `/historique` n'est pas préfixé par `/analyses`, c'est une ressource à
# part entière — même découpage que `api_compte.py` côté module Auth.
router = APIRouter(prefix="/historique", tags=["historique"])

_PAGE_SIZE_DEFAUT = 20
_PAGE_SIZE_MAX = 100


class EntreeHistoriqueReponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "resultat_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
                "input_text": "Contribue surtout à des side-projects Python le week-end.",
                "created_at": "2026-08-18T10:00:00Z",
            }
        }
    )

    id: uuid.UUID
    # Id de l'analyse à suivre pour afficher le résultat complet
    # (`GET /analyses/{resultat_id}/statut`) — c'est le lien attendu par
    # K6 (backlog.md) vers `/analyse/[id]`.
    resultat_id: uuid.UUID
    input_text: str
    created_at: datetime

    @classmethod
    def depuis_domaine(cls, entree: EntreeHistorique) -> "EntreeHistoriqueReponse":
        return cls(
            id=entree.id,
            resultat_id=entree.resultat_id,
            input_text=entree.input_text,
            created_at=entree.created_at,
        )


class HistoriquePageReponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                        "resultat_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
                        "input_text": "Contribue surtout à des side-projects Python le week-end.",
                        "created_at": "2026-08-18T10:00:00Z",
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 20,
            }
        }
    )

    items: list[EntreeHistoriqueReponse]
    total: int
    page: int
    page_size: int


def _lister_historique(request: Request) -> ListerHistorique:
    # Résolu à chaque requête : même motif que `_generer_analyse`
    # (modules/analyse/adaptateurs/api.py).
    registry = request.app.state.registry
    return ListerHistorique(depot=registry.resolve(DépôtHistoriquePort))


@router.get(
    "",
    response_model=HistoriquePageReponse,
    summary="Consulter son historique personnel",
    response_description=(
        "Page de l'historique de l'appelant authentifié, du plus récent au plus ancien."
    ),
    responses=responses_erreur(
        (
            401,
            "non_authentifie",
            "Authentification requise.",
            "Aucun jeton présenté, ou jeton invalide/expiré.",
        ),
    ),
)
async def lister_historique(
    use_case: ListerHistorique = Depends(_lister_historique),
    user_id: uuid.UUID = Depends(get_current_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=_PAGE_SIZE_DEFAUT, ge=1, le=_PAGE_SIZE_MAX),
) -> HistoriquePageReponse:
    # `user_id` vient exclusivement du JWT (`get_current_user`, C7), jamais
    # d'un paramètre de requête (agents.md §7, explicitement cité par ce
    # ticket H3) : impossible de consulter l'historique de quelqu'un d'autre
    # en changeant un paramètre côté client.
    entrees, total = await use_case.executer(user_id, page, page_size)
    return HistoriquePageReponse(
        items=[EntreeHistoriqueReponse.depuis_domaine(entree) for entree in entrees],
        total=total,
        page=page,
        page_size=page_size,
    )
