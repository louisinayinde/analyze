from modules.auth.adaptateurs.api import get_current_user, get_current_user_optional, router
from modules.auth.adaptateurs.api_compte import router as router_compte

# Seule surface publique du module (agents.md §4) : `composition/app.py`
# importe `router` d'ici, jamais directement `modules.auth.adaptateurs.api`.
# `get_current_user` (C7) est exposée pour les mêmes raisons : les futurs
# modules protégés (D, H) doivent pouvoir écrire
# `Depends(get_current_user)` sans jamais importer `adaptateurs.api`.
# `get_current_user_optional` (D4) sert les routes qui acceptent un
# appelant anonyme ou authentifié, `POST /analyses` en premier lieu.
# `router_compte` (H3) porte `DELETE /compte` sur un second `APIRouter`,
# distinct de `router` (flux d'auth) — même découpage que `router`/
# `router_interne` côté module Analyse.
__all__ = ["get_current_user", "get_current_user_optional", "router", "router_compte"]
