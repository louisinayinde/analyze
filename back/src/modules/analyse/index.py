from modules.analyse.adaptateurs.api import router
from modules.analyse.adaptateurs.stockage_image_factice import StockageImageFactice
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
# le use-case `GenererAnalyse`. D4 y ajoute `router` (POST /analyses) ainsi
# que `StockageImageFactice`, adaptateur provisoire câblé au point de
# composition en attendant E5 — même rôle que `GenerateurIAFactice` (D1,
# exposé par `modules.ia.index`) vis-à-vis de `GenerateurIAPort`. D5 y
# ajoute le use-case `ObtenirStatutAnalyse` ; `router` porte désormais
# aussi `GET /analyses/{id}/statut`, sur le même `APIRouter` que D4.
__all__ = [
    "Analyse",
    "CachePort",
    "GenerateurIAPort",
    "GenererAnalyse",
    "ObtenirStatutAnalyse",
    "SourceAnalyse",
    "StatutAnalyse",
    "StockageImageFactice",
    "StockageImagePort",
    "router",
]
