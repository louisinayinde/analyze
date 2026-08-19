output "jwt_signing_key_secret_id" {
  description = "ID de la ressource Secret Manager pour la clé de signature JWT — utilisé par le module iam (L6) pour les permissions et par compute (L7) pour brancher la variable d'environnement JWT_SIGNING_KEY."
  value       = google_secret_manager_secret.jwt_signing_key.secret_id
}

output "llm_api_key_secret_id" {
  description = "ID de la ressource Secret Manager pour la clé API LLM (Anthropic) — accès réservé au service worker (L6, backlog.md), jamais au frontend."
  value       = google_secret_manager_secret.llm_api_key.secret_id
}

output "database_url_secret_id" {
  description = "ID de la ressource Secret Manager pour DATABASE_URL — consommé par les services api et worker (L7), jamais par le frontend."
  value       = google_secret_manager_secret.database_url.secret_id
}
