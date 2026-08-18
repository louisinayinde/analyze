from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from shared.correlation import CORRELATION_ID_HEADER, get_correlation_id
from shared.errors import ErreurAPI, ErreurDomaine


def configure_error_handling(app: FastAPI) -> None:
    """Centralise le mapping exception → réponse HTTP (agents.md §4, §9).

    Un seul endroit connaît la correspondance entre une exception et son
    code HTTP : une route lève une `ErreurDomaine` (ou laisse une exception
    FastAPI standard remonter) et n'a jamais à formatter sa propre réponse
    d'erreur ni à dupliquer un try/except (agents.md §6).

    Extrait de `composition/app.py` (F2, backlog.md) pour être réutilisé
    tel quel par `composition/worker.py` : les deux processus doivent
    renvoyer la même enveloppe d'erreur JSON, sans dupliquer ce mapping
    (agents.md §1, DRY — même connaissance, un seul endroit).
    """

    @app.exception_handler(ErreurDomaine)
    async def _erreur_domaine(request: Request, exc: ErreurDomaine) -> JSONResponse:
        return _reponse_erreur(request, exc.status_code, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _erreur_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _reponse_erreur(request, exc.status_code, "erreur_http", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _erreur_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _reponse_erreur(
            request,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "entree_invalide",
            "La requête ne respecte pas le format attendu.",
        )

    @app.exception_handler(Exception)
    async def _erreur_inattendue(request: Request, exc: Exception) -> JSONResponse:
        # Remplace le comportement par défaut de Starlette (page 500 non
        # formattée) par la même enveloppe JSON que le reste des erreurs.
        # Pas de log ici : CorrelationIdMiddleware (shared/correlation.py)
        # journalise déjà la trace complète avant que cette exception ne
        # remonte jusqu'ici — un second appel ferait un doublon (agents.md §2).
        return _reponse_erreur(
            request,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "erreur_interne",
            "Une erreur inattendue est survenue.",
        )


def _reponse_erreur(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
    # `request.state.correlation_id` (posé par CorrelationIdMiddleware avant
    # tout traitement) est la source fiable : contrairement au contextvar,
    # il survit même quand ce handler s'exécute après coup, au niveau du
    # middleware le plus externe (cas du handler `Exception` ci-dessus).
    correlation_id = getattr(request.state, "correlation_id", None) or get_correlation_id()
    erreur = ErreurAPI(code=code, message=message, correlation_id=correlation_id)
    response = JSONResponse(status_code=status_code, content=erreur.model_dump())
    response.headers[CORRELATION_ID_HEADER] = correlation_id
    return response
