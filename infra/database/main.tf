# API nécessaire à ce module pour piloter Cloud SQL. Activée ici (pas dans
# bootstrap.sh) : spécifique à la base, pas au bootstrap ponctuel de l'état.
resource "google_project_service" "sqladmin" {
  project = var.project_id
  service = "sqladmin.googleapis.com"

  disable_on_destroy = false
}

# État du module network (L2) : on lit son VPC plutôt que de redupliquer son
# ID en dur (convention documentée dans infra/README.md). Le peering Private
# Service Access créé par L2 doit déjà être appliqué : sans lui, la création
# de l'instance ci-dessous échoue côté Cloud SQL (voir le commentaire sur ce
# peering dans infra/network/main.tf).
data "terraform_remote_state" "network" {
  backend = "gcs"
  config = {
    bucket = "analyze-app-prod-tfstate"
    prefix = "network"
  }
}

# Mot de passe généré côté Terraform, jamais en dur. Il ne transite que dans
# l'état Terraform (bucket privé + chiffrement au repos, cf. infra/README.md)
# et dans l'output sensitive ci-dessous — jamais dans le code versionné
# (agents.md §7). Le module secrets (L5) le reprendra pour l'écrire dans
# Secret Manager ; en attendant cet output est la seule source de vérité.
resource "random_password" "app_db_password" {
  length  = 32
  special = false # évite les soucis d'échappement dans une DATABASE_URL
}

# Instance Cloud SQL Postgres. Un seul environnement (projets.md) : pas de
# réplique HA multi-zone, pas de réplicas de lecture — le chemin vers ça est
# documenté, pas préconstruit (agents.md §2, §9).
resource "google_sql_database_instance" "main" {
  name             = "analyze-db"
  project          = var.project_id
  region           = var.region
  database_version = "POSTGRES_16" # aligné sur postgres:16-alpine en local (docker-compose.yml)

  # Priorité 1 de agents.md §13 (sûreté des données) : un `terraform destroy`
  # accidentel ne doit pas pouvoir supprimer la base de prod.
  deletion_protection = true

  settings {
    # Budget serré, un seul dev (agents.md §2) : le tier partagé le moins
    # cher qui tient la charge actuelle. Le chemin vers un tier dédié n'est
    # pas préconstruit : à revoir si `db-f1-micro` montre des signes réels de
    # saturation (CPU/mémoire en observabilité, agents.md §8).
    tier    = "db-f1-micro"
    edition = "ENTERPRISE" # seule édition compatible avec un tier partagé

    # Zonal plutôt que régional (HA) : une instance régionale double la
    # facture pour une disponibilité que ce produit portfolio n'a pas besoin
    # de payer (agents.md §9 — pas de neuf non justifié). Les sauvegardes +
    # PITR ci-dessous couvrent le vrai risque (perte de données), pas la
    # continuité de service en cas de panne de zone.
    availability_type = "ZONAL"

    disk_type       = "PD_SSD"
    disk_size       = 10   # Go — minimum utile, l'autoresize prend le relais
    disk_autoresize = true # évite la corvée manuelle de resize (agents.md §9)

    # Sauvegardes automatiques + PITR : exigence explicite du ticket L3.
    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7       # maximum permis en édition ENTERPRISE
      start_time                     = "02:00" # heure creuse UTC

      backup_retention_settings {
        retained_backups = 7
        retention_unit   = "COUNT"
      }
    }

    ip_configuration {
      ipv4_enabled    = false # pas d'IP publique sur la base (projets.md)
      private_network = data.terraform_remote_state.network.outputs.network_id
    }
  }

  depends_on = [google_project_service.sqladmin]
}

# Base applicative unique, alignée sur POSTGRES_DB=app en local (.env.example).
resource "google_sql_database" "app" {
  name     = "app"
  project  = var.project_id
  instance = google_sql_database_instance.main.name
}

# Utilisateur applicatif unique, aligné sur POSTGRES_USER=app en local. Pas de
# séparation de rôles supplémentaire pour l'instant (KISS/YAGNI, agents.md
# §1) — à revisiter si un besoin réel de séparation de privilèges apparaît.
resource "google_sql_user" "app" {
  name     = "app"
  project  = var.project_id
  instance = google_sql_database_instance.main.name
  password = random_password.app_db_password.result
}
