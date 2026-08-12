import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from logging import getLogger

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

CORRELATION_ID_HEADER = "X-Correlation-ID"

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")

_logger = getLogger("http")


def get_correlation_id() -> str:
    """Le correlation_id de la requête en cours (agents.md §9), lu par le formatter JSON."""
    return _correlation_id.get()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Génère/propage le correlation_id et journalise chaque requête traitée.

    Le header entrant fait foi s'il est présent (propagation front → api →
    worker, agents.md §3) ; sinon un identifiant est généré. Le stocker dans
    un contextvar le rend disponible à tout logger appelé pendant la requête
    sans avoir à le faire passer explicitement à travers les couches.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid.uuid4())
        # Sur `request.state` en plus du contextvar : un handler enregistré
        # pour `Exception` (shared/errors.py) est promu par Starlette au
        # niveau du middleware le plus externe, qui s'exécute après que ce
        # `dispatch` ait fini (donc après le `reset()` du contextvar dans le
        # `finally` ci-dessous). `request.state` survit à ce déroulement, pas
        # le contextvar.
        request.state.correlation_id = correlation_id
        token = _correlation_id.set(correlation_id)
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            _logger.exception(
                "request_failed",
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            raise
        else:
            duration_ms = (time.perf_counter() - start) * 1000
            response.headers[CORRELATION_ID_HEADER] = correlation_id
            _logger.info(
                "request_handled",
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "http_status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            return response
        finally:
            _correlation_id.reset(token)
