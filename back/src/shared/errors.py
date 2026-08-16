from pydantic import BaseModel


class ErreurAPI(BaseModel):
    """Format de réponse unique pour toute erreur API (agents.md §3, §9).

    `code` est un identifiant stable destiné aux clients (jamais le message,
    qui peut changer sans préavis) ; `correlation_id` permet de retrouver la
    requête dans les logs structurés (shared/logging.py).
    """

    code: str
    message: str
    correlation_id: str


class ErreurDomaine(Exception):
    """Base des exceptions métier, mappées vers un code HTTP une fois pour toutes.

    Une route (ou un cas d'usage appelé par une route) lève une sous-classe
    et n'a jamais besoin de son propre try/except pour formatter une
    réponse : le mapping exception → HTTP est centralisé dans
    composition/app.py (agents.md §4 — pas de logique de framework dans le
    domaine ; agents.md §6 — pas de try/except dupliqué par route).
    """

    code: str = "erreur_interne"
    status_code: int = 500
    message_par_defaut: str = "Une erreur est survenue."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message_par_defaut
        super().__init__(self.message)


class RessourceIntrouvable(ErreurDomaine):
    code = "ressource_introuvable"
    status_code = 404
    message_par_defaut = "La ressource demandée est introuvable."


class ConflitRessource(ErreurDomaine):
    code = "conflit_ressource"
    status_code = 409
    message_par_defaut = "La ressource est dans un état incompatible avec cette opération."


class EntreeInvalide(ErreurDomaine):
    code = "entree_invalide"
    status_code = 422
    message_par_defaut = "La requête ne respecte pas le format attendu."


class NonAuthentifie(ErreurDomaine):
    code = "non_authentifie"
    status_code = 401
    message_par_defaut = "Authentification requise."


class AccesRefuse(ErreurDomaine):
    code = "acces_refuse"
    status_code = 403
    message_par_defaut = "Accès refusé."


class ServiceIndisponible(ErreurDomaine):
    """Levée quand une dépendance externe est en incident (E4, backlog.md).

    503, pas 500 : contrairement à `erreur_interne` (bug de notre côté),
    ce cas est prévisible et temporaire — le client sait qu'il peut
    retenter plus tard. Levée notamment par `CircuitBreaker`
    (modules/ia/adaptateurs/circuit_breaker.py) quand le circuit est
    ouvert, plutôt que de laisser un timeout brut remonter (agents.md §3 —
    isoler la panne, pas la propager).
    """

    code = "service_indisponible"
    status_code = 503
    message_par_defaut = (
        "Le service est temporairement indisponible, réessaie dans quelques minutes."
    )
