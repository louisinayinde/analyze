from modules.ratelimit.adaptateurs.limiteur_debit_postgres import LimiteurDebitPostgres

# Seule surface publique du module (agents.md §4). G1 n'expose que
# l'adaptateur Postgres du `RateLimiterPort` (modules/ratelimit/ports/
# rate_limiter.py, importé directement par son chemin au point de
# composition — même convention que `CachePort`/`GenerateurIAPort`,
# composition/app.py). G2/G3 y ajouteront le middleware qui consomme ce
# port sans jamais importer `limiteur_debit_postgres` directement.
__all__ = ["LimiteurDebitPostgres"]
