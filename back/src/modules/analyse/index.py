from modules.analyse.domaine.analyse import Analyse, SourceAnalyse, StatutAnalyse
from modules.analyse.ports.cache import CachePort
from modules.analyse.ports.generateur_ia import GenerateurIAPort
from modules.analyse.ports.stockage_image import StockageImagePort

# Seule surface publique du module (agents.md §4). D1 n'expose encore aucun
# router ni use-case (ça viendra en D3/D4/D5) : uniquement l'entité, son
# vocabulaire (`SourceAnalyse`, `StatutAnalyse`) et les trois ports, dont
# les futurs adaptateurs (D2 pour `CachePort`, E1/E2 pour `GenerateurIAPort`,
# E5 pour `StockageImagePort`) ont besoin pour implémenter ces contrats
# sans jamais importer un fichier interne de `domaine/` ou `ports/`.
__all__ = [
    "Analyse",
    "CachePort",
    "GenerateurIAPort",
    "SourceAnalyse",
    "StatutAnalyse",
    "StockageImagePort",
]
