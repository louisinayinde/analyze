from typing import Any

from shared.errors import ErreurAPI


def responses_erreur(*erreurs: tuple[int, str, str, str]) -> dict[int | str, dict[str, Any]]:
    """Construit les entrées `responses=` FastAPI documentant les erreurs
    qu'une route peut réellement lever (H1, backlog.md ; agents.md §3 : le
    contrat OpenAPI est la source de vérité, pas le code).

    Centralise la forme d'une entrée de réponse d'erreur (schéma `ErreurAPI`
    + exemple JSON) pour que chaque route ne la redéfinisse pas à la main :
    même connaissance — la forme d'une erreur API, déjà définie une seule
    fois dans `shared/errors.py` — appliquée à chaque endpoint (agents.md
    §1, DRY). Chaque tuple est `(status_code, code, message_exemple,
    description)` : `code`/`message_exemple` correspondent à une exception
    `ErreurDomaine` réellement levée sur ce chemin (`shared/errors.py`),
    jamais une liste générique de statuts possibles en théorie.
    """
    return {
        status_code: {
            "model": ErreurAPI,
            "description": description,
            "content": {
                "application/json": {
                    "example": {
                        "code": code,
                        "message": message_exemple,
                        "correlation_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    }
                }
            },
        }
        for status_code, code, message_exemple, description in erreurs
    }
