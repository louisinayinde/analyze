output "instance_connection_name" {
  description = "Nom de connexion Cloud SQL (project:region:instance) — utile pour le Cloud SQL Auth Proxy en usage ponctuel (ex. migrations Alembic depuis un poste local)."
  value       = google_sql_database_instance.main.connection_name
}

output "private_ip_address" {
  description = "IP privée de l'instance, joignable depuis Cloud Run via le connecteur VPC (module network, L2). Aucune IP publique n'existe (projets.md)."
  value       = google_sql_database_instance.main.private_ip_address
}

output "database_name" {
  description = "Nom de la base applicative."
  value       = google_sql_database.app.name
}

output "database_user" {
  description = "Nom de l'utilisateur applicatif."
  value       = google_sql_user.app.name
}

output "database_password" {
  description = "Mot de passe généré de l'utilisateur applicatif — à écrire dans Secret Manager par le module secrets (L5), jamais consommé en clair ailleurs."
  value       = random_password.app_db_password.result
  sensitive   = true
}
