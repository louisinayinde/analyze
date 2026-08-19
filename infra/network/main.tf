# APIs nécessaires à ce module. Activées ici (pas dans bootstrap.sh) : elles
# sont spécifiques au réseau, pas au bootstrap ponctuel de l'état Terraform.
resource "google_project_service" "compute" {
  project = var.project_id
  service = "compute.googleapis.com"

  disable_on_destroy = false
}

resource "google_project_service" "service_networking" {
  project = var.project_id
  service = "servicenetworking.googleapis.com"

  disable_on_destroy = false
}

resource "google_project_service" "vpc_access" {
  project = var.project_id
  service = "vpcaccess.googleapis.com"

  disable_on_destroy = false
}

# VPC dédié au produit, sans subnets automatiques : on ne crée que ce dont on
# a réellement besoin (agents.md §1, KISS/YAGNI), pas un /20 par région GCP.
resource "google_compute_network" "vpc" {
  name                    = "analyze-vpc"
  auto_create_subnetworks = false

  depends_on = [google_project_service.compute]
}

# Plage d'adresses réservée pour le peering "Private Service Access" avec les
# services managés Google — Cloud SQL en fait partie. C'est ce qui permet à
# la base de n'avoir AUCUNE IP publique (projets.md) : elle n'est tout
# simplement pas joignable depuis internet, pas juste protégée par un
# firewall qu'on pourrait mal configurer.
resource "google_compute_global_address" "private_service_range" {
  name          = "analyze-private-service-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

# Le peering lui-même. Le module database (L3) créera l'instance Cloud SQL
# avec `private_network = <id de ce VPC>` : cette connexion doit exister
# avant, sinon la création de l'instance échoue côté Cloud SQL.
resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_service_range.name]

  depends_on = [google_project_service.service_networking]
}

# Connecteur d'accès VPC serverless : le seul moyen pour Cloud Run (services
# api/worker, module compute L7) d'atteindre une IP privée dans ce VPC. Sans
# lui, "pas d'IP publique sur la base" rendrait la base injoignable depuis
# l'API elle-même. Plage dédiée (10.8.0.0/28), distincte de celle du peering
# ci-dessus (10.10.0.0/16) pour éviter tout chevauchement.
#
# Coût : ce connecteur fait tourner en continu 2 à 3 petites instances, même
# hors trafic — c'est le prix de la connectivité privée. Budget serré
# (agents.md §2) → machine la moins chère disponible et plafond bas, plutôt
# que les valeurs par défaut (2 à 10 instances).
resource "google_vpc_access_connector" "connector" {
  name          = "analyze-cloudsql-conn"
  region        = var.region
  network       = google_compute_network.vpc.name
  ip_cidr_range = "10.8.0.0/28"

  machine_type  = "f1-micro"
  min_instances = 2
  max_instances = 3

  depends_on = [google_project_service.vpc_access]
}
