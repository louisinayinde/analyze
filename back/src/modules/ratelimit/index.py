from modules.ratelimit.adaptateurs.api import limiter_debit_ip_anonyme
from modules.ratelimit.adaptateurs.limiteur_debit_postgres import LimiteurDebitPostgres

# Seule surface publique du module (agents.md §4). G1 expose l'adaptateur
# Postgres du `RateLimiterPort` (modules/ratelimit/ports/rate_limiter.py,
# importé directement par son chemin au point de composition — même
# convention que `CachePort`/`GenerateurIAPort`, composition/app.py). G2
# ajoute `limiter_debit_ip_anonyme`, la dépendance FastAPI que
# `modules/analyse/adaptateurs/api.py` branche sur `POST /analyses` — même
# motif que `get_current_user`/`get_current_user_optional`
# (modules/auth/index.py) : un autre module consomme le port par cette
# dépendance publique, jamais en important `adaptateurs/api.py`
# directement. G3 y ajoutera son équivalent par `user_id`.
__all__ = ["LimiteurDebitPostgres", "limiter_debit_ip_anonyme"]
