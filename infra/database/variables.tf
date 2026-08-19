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
