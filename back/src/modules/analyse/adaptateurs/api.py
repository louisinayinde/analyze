import logging
import uuid

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field

from modules.analyse.application.generer_analyse import GenererAnalyse
from modules.analyse.domaine.analyse import Analyse, SourceAnalyse, StatutAnalyse
from modules.analyse.ports.cache import CachePort
from modules.analyse.ports.generateur_ia import GenerateurIAPort
from modules.analyse.ports.stockage_image import StockageImagePort
from modules.auth.index import get_current_user_optional

# Adaptateur d'entrée (driving adapter, agents.md §4) : seul fichier du
# module Analyse qui connaît FastAPI. Traduit HTTP <-> cas d'usage `
# GenererAnalyse` (D3), lui-même ignorant du framework. Câblé au point de
# composition via `index.py` (composition/app.py, D4).
router = APIRouter(prefix="/analyses", tags=["analyse"])

# projets.md §Backend : « validation stricte de la longueur du texte en
# entrée (ex. 5000 caractères max) — borne le coût d'un appel et limite
# l'abus ». `min_length=1` couvre la borne basse de la même règle (une
# entrée vide n'a rien à analyser) ; le rejet du contenu whitespace-only et
# la sanitisation anti prompt-injection sont un renforcement volontairement
# laissé à D7 (backlog.md), pas une validation de longueur.
TEXTE_LONGUEUR_MAX = 5000

_logger = logging.getLogger("analyse")


class AnalyseRequete(BaseModel):
    texte: str = Field(min_length=1, max_length=TEXTE_LONGUEUR_MAX)
    source_type: SourceAnalyse


class AnalyseTermineeReponse(BaseModel):
    """Réponse `200` — le résultat est immédiatement disponible (cache-hit,
    ou première génération déjà terminée avant que ce ticket ne branche le
    job asynchrone réel, voir F1).
    """

    id: uuid.UUID
    statut: StatutAnalyse
    resultat_texte: str | None
    resultat_image_url: str | None

    @classmethod
    def depuis_domaine(cls, analyse: Analyse) -> "AnalyseTermineeReponse":
        return cls(
            id=analyse.id,
            statut=analyse.statut,
            resultat_texte=analyse.resultat_texte,
            resultat_image_url=analyse.resultat_image_url,
        )


class AnalyseEnAttenteReponse(BaseModel):
    """Réponse `202` — le résultat n'est pas encore prêt, le client poll
    `GET /analyses/{id}/statut` (D5) avec ce `job_id`.
    """

    job_id: uuid.UUID


def _generer_analyse(request: Request) -> GenererAnalyse:
    # Résolu à chaque requête (et non une fois à la création du router) :
    # les adaptateurs ne sont câblés dans le registre qu'au lifespan de
    # l'app (composition/app.py), après le montage des routers — même
    # motif que `modules/auth/adaptateurs/api.py`.
    registry = request.app.state.registry
    return GenererAnalyse(
        cache=registry.resolve(CachePort),
        generateur_ia=registry.resolve(GenerateurIAPort),
        stockage_image=registry.resolve(StockageImagePort),
    )


@router.post("", response_model=AnalyseTermineeReponse | AnalyseEnAttenteReponse)
async def creer_analyse(
    corps: AnalyseRequete,
    reponse_http: Response,
    use_case: GenererAnalyse = Depends(_generer_analyse),
    user_id: uuid.UUID | None = Depends(get_current_user_optional),
) -> AnalyseTermineeReponse | AnalyseEnAttenteReponse:
    analyse = await use_case.executer(corps.texte, corps.source_type)

    # Le statut renvoyé par le use-case (D3) décide seul du code HTTP : pas
    # de branchement sur le fait que cet appel ait ou non créé la ligne de
    # cache. Une fois F1 branché, un cache-miss frais laissera aussi le
    # statut à `pending` (job dispatché de façon réellement asynchrone) et
    # tombera naturellement dans la même branche `202` ci-dessous, sans
    # qu'il faille toucher ce fichier (agents.md §4).
    if analyse.statut is StatutAnalyse.DONE:
        _logger.info(
            "analyse_disponible",
            extra={"analyse_id": str(analyse.id), "user_id": str(user_id) if user_id else None},
        )
        return AnalyseTermineeReponse.depuis_domaine(analyse)

    reponse_http.status_code = status.HTTP_202_ACCEPTED
    _logger.info(
        "analyse_en_cours",
        extra={"analyse_id": str(analyse.id), "user_id": str(user_id) if user_id else None},
    )
    return AnalyseEnAttenteReponse(job_id=analyse.id)
