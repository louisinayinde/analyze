import logging
import uuid

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel

from modules.analyse.application.generer_analyse import GenererAnalyse
from modules.analyse.application.obtenir_statut_analyse import ObtenirStatutAnalyse
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

# La validation du texte (longueur, vide/whitespace, sanitisation
# anti prompt-injection grossière — D7, backlog.md) vit entièrement dans
# `valider_et_nettoyer_texte` (domaine, agents.md §4) et est appliquée par
# le use-case (D3), pas ici : même posture que `mot_de_passe.valider_robustesse`
# côté module Auth — une seule source de vérité pour la règle (agents.md §1),
# appliquée à tout appelant du use-case, pas seulement à cette route. Ce
# modèle Pydantic ne valide donc que la *forme* de la requête HTTP
# (présence des champs, type), jamais les règles métier.
_logger = logging.getLogger("analyse")


class AnalyseRequete(BaseModel):
    texte: str
    source_type: SourceAnalyse


class AnalyseTermineeReponse(BaseModel):
    """Réponse `200` de `POST /analyses` — le résultat est immédiatement
    disponible (cache-hit, ou première génération déjà terminée avant que
    ce ticket ne branche le job asynchrone réel, voir F1).

    Réutilisée telle quelle comme réponse de `GET /analyses/{id}/statut`
    (D5) : c'est exactement la forme `pending | done | failed (+ résultat
    si done)` demandée par ce ticket, `statut` portant `PENDING`/`FAILED`
    avec les deux champs résultat à `None` dans ces cas.
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


def _obtenir_statut_analyse(request: Request) -> ObtenirStatutAnalyse:
    # Même motif de résolution différée que `_generer_analyse` ci-dessus.
    registry = request.app.state.registry
    return ObtenirStatutAnalyse(cache=registry.resolve(CachePort))


@router.get("/{analyse_id}/statut", response_model=AnalyseTermineeReponse)
async def obtenir_statut_analyse(
    analyse_id: uuid.UUID,
    use_case: ObtenirStatutAnalyse = Depends(_obtenir_statut_analyse),
) -> AnalyseTermineeReponse:
    # Pas d'authentification requise (D5, agents.md §7 : rien de sensible
    # n'est exposé — `job_id` est un UUID non énumérable, le texte source
    # lui-même n'est jamais retourné, cf. `CachePort.obtenir_par_id`) —
    # même posture que `POST /analyses` (D4) : le polling K3 ne doit
    # dépendre d'aucune page d'auth.
    analyse = await use_case.executer(analyse_id)
    return AnalyseTermineeReponse.depuis_domaine(analyse)
