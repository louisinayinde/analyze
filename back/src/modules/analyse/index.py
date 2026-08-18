from modules.analyse.adaptateurs.api import router
from modules.analyse.adaptateurs.api_worker import router_interne
from modules.analyse.adaptateurs.file_jobs_cloud_tasks import FileJobsCloudTasks
from modules.analyse.adaptateurs.file_jobs_en_processus_immediat import (
    FileJobsEnProcessusImmediat,
)
from modules.analyse.adaptateurs.stockage_image_filesystem import StockageImageFilesystem
from modules.analyse.adaptateurs.stockage_image_gcs import StockageImageGCS
from modules.analyse.application.executer_job_generation import ExecuterJobGeneration
from modules.analyse.application.generer_analyse import GenererAnalyse
from modules.analyse.application.obtenir_statut_analyse import ObtenirStatutAnalyse
from modules.analyse.domaine.analyse import Analyse, SourceAnalyse, StatutAnalyse
from modules.analyse.ports.cache import CachePort
from modules.analyse.ports.file_jobs import FileJobsPort
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
# que l'adaptateur dev est réel et tout aussi gratuit à faire tourner. F1 y
# ajoute `FileJobsPort` (le port branché dans `GenererAnalyse` à la place
# de l'appel direct provisoire de D3), ses deux adaptateurs —
# `FileJobsEnProcessusImmediat` (dev) et `FileJobsCloudTasks` (prod, activé
# après L7) — et `ExecuterJobGeneration`, la génération elle-même (appel
# IA + stockage image), extraite de D3 pour devenir le corps du job
# invoqué par l'adaptateur `FileJobsPort` retenu. F3 y ajoute
# `router_interne` (POST /internal/jobs/analyses) : l'endpoint que le
# `worker` (composition/worker.py) expose à Cloud Tasks, distinct de
# `router` (jamais monté sur `worker`, réservé à `api`).
__all__ = [
    "Analyse",
    "CachePort",
    "ExecuterJobGeneration",
    "FileJobsCloudTasks",
    "FileJobsEnProcessusImmediat",
    "FileJobsPort",
    "GenerateurIAPort",
    "GenererAnalyse",
    "ObtenirStatutAnalyse",
    "SourceAnalyse",
    "StatutAnalyse",
    "StockageImageFilesystem",
    "StockageImageGCS",
    "StockageImagePort",
    "router",
    "router_interne",
]
