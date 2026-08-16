from modules.analyse.adaptateurs.api import router
from modules.analyse.adaptateurs.stockage_image_filesystem import StockageImageFilesystem
from modules.analyse.adaptateurs.stockage_image_gcs import StockageImageGCS
from modules.analyse.application.generer_analyse import GenererAnalyse
from modules.analyse.application.obtenir_statut_analyse import ObtenirStatutAnalyse
from modules.analyse.domaine.analyse import Analyse, SourceAnalyse, StatutAnalyse
from modules.analyse.ports.cache import CachePort
from modules.analyse.ports.generateur_ia import GenerateurIAPort
from modules.analyse.ports.stockage_image import StockageImagePort

# Seule surface publique du module (agents.md §4). D1 expose l'entité, son
# vocabulaire (`SourceAnalyse`, `StatutAnalyse`) et les trois ports, dont
# les adaptateurs (D2 pour `CachePort`, E1/E2 pour `GenerateurIAPort`, E5
# pour `StockageImagePort`) ont besoin pour implémenter ces contrats sans
# jamais importer un fichier interne de `domaine/` ou `ports/`. D3 y ajoute
# le use-case `GenererAnalyse`. D4 y ajoute `router` (POST /analyses). D5 y
# ajoute le use-case `ObtenirStatutAnalyse` ; `router` porte désormais
# aussi `GET /analyses/{id}/statut`, sur le même `APIRouter` que D4. E5 y
# ajoute les deux adaptateurs réels de `StockageImagePort` —
# `StockageImageFilesystem` (dev) et `StockageImageGCS` (prod, activé après
# L4) — et retire `StockageImageFactice` (D4), devenue inutile maintenant
# que l'adaptateur dev est réel et tout aussi gratuit à faire tourner.
__all__ = [
    "Analyse",
    "CachePort",
    "GenerateurIAPort",
    "GenererAnalyse",
    "ObtenirStatutAnalyse",
    "SourceAnalyse",
    "StatutAnalyse",
    "StockageImageFilesystem",
    "StockageImageGCS",
    "StockageImagePort",
    "router",
]
