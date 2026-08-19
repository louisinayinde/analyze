output "frontend_service_account_email" {
  description = "Email du service account dédié au service Cloud Run frontend — aucun accès DB/secrets/bucket. À brancher sur google_cloud_run_v2_service.frontend (module compute, L7)."
  value       = google_service_account.frontend.email
}

output "api_service_account_email" {
  description = "Email du service account dédié au service Cloud Run api — accès en lecture à database-url et jwt-signing-key. À brancher sur google_cloud_run_v2_service.api (module compute, L7)."
  value       = google_service_account.api.email
}

output "worker_service_account_email" {
  description = "Email du service account dédié au service Cloud Run worker — seul service avec accès en lecture à llm-api-key et en écriture au bucket images. À brancher sur google_cloud_run_v2_service.worker (module compute, L7)."
  value       = google_service_account.worker.email
}
