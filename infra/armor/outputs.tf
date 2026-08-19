output "api_lb_ip" {
  description = "IP statique globale du Load Balancer devant api. Sert à construire le domaine nip.io (voir api_lb_url)."
  value       = google_compute_global_address.api_lb.address
}

output "api_lb_url" {
  description = "URL publique HTTPS du service api via le LB + Cloud Armor. À repasser en `-var api_public_url=<valeur>` (avec `-var restrict_api_ingress=true`) au module compute pour basculer NEXT_PUBLIC_API_URL/API_INTERNAL_URL dessus et fermer l'accès direct *.run.app (voir infra/README.md)."
  value       = "https://${local.api_lb_domain}"
}

output "security_policy_id" {
  description = "ID de la policy Cloud Armor (référencée par O3, backlog.md, pour le test de charge/abus)."
  value       = google_compute_security_policy.api.id
}
