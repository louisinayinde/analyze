variable "project_id" {
  description = "ID du projet GCP cible."
  type        = string
  default     = "analyze-app-prod"
}

variable "region" {
  description = "Région GCP par défaut pour les ressources régionales."
  type        = string
  default     = "europe-west1"
}

# --- Casse le cycle CORS api <-> frontend ---
# `api` a besoin de l'URL de `frontend` pour restreindre `CORS_ORIGINS`
# (agents.md §7 — jamais de wildcard avec `allow_credentials=True`, cf.
# composition/app.py._configure_cors) ; `frontend` a besoin de l'URL de
# `api` pour l'appeler (NEXT_PUBLIC_API_URL/API_INTERNAL_URL). Les deux ne
# peuvent pas se référencer l'un l'autre dans le même apply Terraform (cycle
# de dépendances), donc `frontend` dépend réellement de la sortie
# `google_cloud_run_v2_service.api` mais `api` ne dépend que de cette
# variable, jamais de la ressource `frontend`.
#
# Vide par défaut -> `CORS_ORIGINS=""` -> aucune origine autorisée (défaut
# fermé, agents.md §7 — jamais un wildcard par défaut). Premier `apply` :
# crée les trois services, `frontend_url` reste vide. Relever l'URL du
# service frontend (`terraform output frontend_url`) puis refaire
# `terraform apply -var frontend_url=<url>` pour que le CORS de `api`
# s'ouvre réellement. Même logique que le bootstrap du bucket d'état
# (infra/README.md) : une brique où l'ordre naturel des dépendances ne
# suffit pas, donc une étape manuelle explicite plutôt qu'un contournement
# fragile.
variable "frontend_url" {
  description = "URL publique du service Cloud Run frontend, pour CORS_ORIGINS côté api. Vide au premier apply (voir commentaire) — à renseigner ensuite avec l'URL réelle."
  type        = string
  default     = ""
}

# --- Images placeholder (M2 pas encore fait) ---
# M2 (backlog.md) construira et poussera les vraies images `frontend`/
# `api`/`worker` dans Artifact Registry (créé par ce module ci-dessous).
# Avant ça, Terraform a besoin d'une image qui existe déjà pour créer le
# service Cloud Run — même problème d'œuf et de poule que le bucket d'état
# (infra/README.md), résolu ici par une image placeholder publique de
# Google plutôt qu'une image locale committée. `lifecycle.ignore_changes`
# sur chaque service (voir main.tf) empêche Terraform de revenir sur
# l'image déployée ensuite par M2/M4 : ce module gère l'existence du
# service, pas son contenu applicatif après le premier déploiement réel.
variable "container_image_frontend" {
  description = "Image du service frontend. Placeholder par défaut, à remplacer par le vrai déploiement M2/M4 (hors Terraform, voir lifecycle.ignore_changes)."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "container_image_api" {
  description = "Image du service api. Placeholder par défaut, à remplacer par le vrai déploiement M2/M4 (hors Terraform, voir lifecycle.ignore_changes)."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "container_image_worker" {
  description = "Image du service worker. Placeholder par défaut, à remplacer par le vrai déploiement M2/M4 (hors Terraform, voir lifecycle.ignore_changes)."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}
