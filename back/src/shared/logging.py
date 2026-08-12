import json
import logging
from datetime import UTC, datetime

from shared.correlation import get_correlation_id

# Attributs qu'un LogRecord porte toujours (calculés une fois, sur une
# instance jetable) : tout le reste vient des `extra={...}` passés par
# l'appelant et doit apparaître tel quel dans le JSON de sortie.
_STANDARD_RECORD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())


class JsonFormatter(logging.Formatter):
    """Sérialise chaque log en une ligne JSON (agents.md §9).

    Inclut systématiquement le correlation_id de la requête en cours, lu
    depuis le contextvar (shared/correlation.py) — l'appelant n'a rien à
    passer explicitement.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id(),
        }

        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_ATTRS:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Bascule tous les logs de l'app (et d'uvicorn) sur le format JSON.

    Remplace les handlers par défaut d'uvicorn au lieu de les cumuler :
    sinon chaque requête serait journalisée deux fois (texte d'uvicorn +
    JSON de l'app). `uvicorn.access` est désactivé plutôt que reformaté :
    CorrelationIdMiddleware produit déjà un log par requête, plus complet
    (correlation_id, durée) — le garder en plus serait du bruit payant
    (agents.md §2, budget de volume de logs).
    """
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # uvicorn configure son propre logging (dictConfig) avant même que cette
    # fonction ne s'exécute. Il coupe la propagation de "uvicorn" vers le
    # root logger (propagate=False) : sans le réactiver ici, les messages de
    # "uvicorn.error" (démarrage/arrêt), enfant de "uvicorn" dans la
    # hiérarchie, ne remonteraient jamais jusqu'à notre handler JSON.
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.handlers = []
    uvicorn_logger.propagate = True
    logging.getLogger("uvicorn.error").handlers = []
    logging.getLogger("uvicorn.access").disabled = True
