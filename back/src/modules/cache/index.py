from modules.cache.adaptateurs.cache_resultat_postgres import CacheResultatPostgres

# Seule surface publique du module (agents.md §4). D2 n'expose que
# l'adaptateur Postgres du `CachePort` défini en D1 (`modules.analyse`) ;
# le point de composition (composition/app.py) importe d'ici, jamais
# directement `modules.cache.adaptateurs.cache_resultat_postgres`.
__all__ = ["CacheResultatPostgres"]
