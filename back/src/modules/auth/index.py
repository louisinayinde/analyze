from modules.auth.adaptateurs.api import get_current_user, router

# Seule surface publique du module (agents.md §4) : `composition/app.py`
# importe `router` d'ici, jamais directement `modules.auth.adaptateurs.api`.
# `get_current_user` (C7) est exposée pour les mêmes raisons : les futurs
# modules protégés (D, H) doivent pouvoir écrire
# `Depends(get_current_user)` sans jamais importer `adaptateurs.api`.
__all__ = ["get_current_user", "router"]
