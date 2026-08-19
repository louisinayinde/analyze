output "images_bucket_name" {
  description = "Nom du bucket GCS des images générées — à utiliser par l'adaptateur StockageImagePort GCS (E5) et par le service account worker (module iam, L6) pour l'accès en écriture."
  value       = google_storage_bucket.images.name
}

output "images_bucket_url" {
  description = "URL gs:// du bucket, référence directe pour le SDK GCS côté worker."
  value       = "gs://${google_storage_bucket.images.name}"
}

output "cdn_ip_address" {
  description = "IP externe statique du load balancer Cloud CDN — préfixe des URLs publiques d'images (http://<ip>/<nom-objet>). HTTP uniquement pour l'instant, voir le commentaire dans main.tf : pas de domaine enregistré pour brancher un certificat managé."
  value       = google_compute_global_address.images_lb_ip.address
}
