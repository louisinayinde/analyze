output "network_id" {
  description = "ID du VPC, à référencer par les modules database (L3) et compute (L7)."
  value       = google_compute_network.vpc.id
}

output "network_name" {
  description = "Nom du VPC."
  value       = google_compute_network.vpc.name
}

output "vpc_access_connector_id" {
  description = "ID du connecteur VPC serverless, à attacher aux services Cloud Run (module compute, L7)."
  value       = google_vpc_access_connector.connector.id
}

output "private_vpc_connection_ready" {
  description = "Nom du réseau une fois le peering Private Service Access établi — sert de signal : le module database (L3) ne doit créer son instance Cloud SQL en IP privée qu'une fois ce peering en place."
  value       = google_service_networking_connection.private_vpc_connection.network
}
