output "frontend_url" {
  description = "URL publique du service Cloud Run frontend. À repasser en `-var frontend_url=<valeur>` lors d'un second apply pour ouvrir CORS_ORIGINS côté api (voir variables.tf)."
  value       = google_cloud_run_v2_service.frontend.uri
}

output "api_url" {
  description = "URL publique du service Cloud Run api — valeur attendue pour NEXT_PUBLIC_API_URL si le frontend est déployé/testé hors de ce module."
  value       = google_cloud_run_v2_service.api.uri
}

output "worker_url" {
  description = "URL interne du service Cloud Run worker (non publique, roles/run.invoker restreint à son propre service account)."
  value       = google_cloud_run_v2_service.worker.uri
}

output "cloud_tasks_queue_id" {
  description = "ID complet de la queue Cloud Tasks (F1/F3, backlog.md)."
  value       = google_cloud_tasks_queue.jobs.id
}

output "artifact_registry_repository" {
  description = "Chemin du dépôt Artifact Registry où M2 doit pousser les images frontend/api/worker (ex. europe-west1-docker.pkg.dev/analyze-app-prod/analyze-app/<service>)."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}
