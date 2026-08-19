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

# Clé API Anthropic (Claude), fournisseur retenu pour E1/E2 (backlog.md).
# Pas de défaut : jamais commitée nulle part, à passer au apply via
# TF_VAR_llm_api_key ou -var (même logique que les champs sensibles sans
# défaut dans shared/config.py, agents.md §7).
variable "llm_api_key" {
  description = "Clé API Anthropic (Claude) à stocker dans Secret Manager."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.llm_api_key) > 0
    error_message = "llm_api_key ne peut pas être vide — ce module ne doit jamais créer de version de secret vide."
  }
}
