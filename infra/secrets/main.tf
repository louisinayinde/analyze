# API nécessaire à ce module pour piloter Secret Manager. Activée ici (pas
# dans bootstrap.sh) : spécifique à ce module, pas au bootstrap ponctuel de
# l'état (même logique que sqladmin dans database/main.tf, compute dans
# storage/main.tf).
resource "google_project_service" "secretmanager" {
  project = var.project_id
  service = "secretmanager.googleapis.com"

  disable_on_destroy = false
}

# --- Clé de signature JWT (C4, agents.md §7) ---
# Générée côté Terraform, jamais en dur — même logique que
# random_password.app_db_password dans database/main.tf. 64 caractères :
# large marge au-dessus du minimum RFC 7518 §3.2 (32) pour HMAC-SHA256,
# recommandé pour une clé qui signe des tokens jusqu'en L7.
resource "random_password" "jwt_signing_key" {
  length  = 64
  special = false # évite les soucis d'échappement en variable d'environnement Cloud Run
}

resource "google_secret_manager_secret" "jwt_signing_key" {
  secret_id = "jwt-signing-key"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_version" "jwt_signing_key" {
  secret      = google_secret_manager_secret.jwt_signing_key.id
  secret_data = random_password.jwt_signing_key.result
}

# --- Clé API LLM (Anthropic Claude, E1/E2) ---
# Contrairement au mot de passe DB et à la clé JWT ci-dessus, cette clé n'est
# pas générable par Terraform : c'est un credential émis par Anthropic. Pas
# de défaut sur la variable (agents.md §7, même logique que les champs
# sensibles sans défaut dans shared/config.py) : sans valeur explicite au
# apply (TF_VAR_llm_api_key ou -var), Terraform échoue plutôt que de créer
# une version de secret vide.
resource "google_secret_manager_secret" "llm_api_key" {
  secret_id = "llm-api-key"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_version" "llm_api_key" {
  secret      = google_secret_manager_secret.llm_api_key.id
  secret_data = var.llm_api_key
}

# --- Credentials base de données (L3) ---
# Le mot de passe applicatif est généré par le module database (L3), jamais
# dupliqué ici (agents.md §1 DRY) : on le lit via son état distant, comme
# database/main.tf le fait déjà pour le VPC de network (L2). Dépendance
# fonctionnelle réelle sur L3 malgré la dépendance de ticket "L1" indiquée
# dans le backlog pour L5 : ce module peut être appliqué seul pour la clé
# JWT et la clé LLM ci-dessus, mais ce secret précis exige que L3 ait déjà
# été appliqué au moins une fois (son état distant doit exister).
data "terraform_remote_state" "database" {
  backend = "gcs"
  config = {
    bucket = "analyze-app-prod-tfstate"
    prefix = "database"
  }
}

resource "google_secret_manager_secret" "database_url" {
  secret_id = "database-url"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

# Assemblée dans le même format que DATABASE_URL en dev local (.env.example,
# driver postgresql+asyncpg) pour que shared/config.py (Settings.database_url)
# n'ait besoin d'aucune variante prod — un seul champ de config, une seule
# forme d'URL. Connexion via l'IP privée de l'instance (pas de proxy Cloud
# SQL Auth) : Cloud Run atteint cette IP via le connecteur VPC du module
# network (L2), déjà la voie utilisée par L3 pour créer l'instance elle-même.
resource "google_secret_manager_secret_version" "database_url" {
  secret = google_secret_manager_secret.database_url.id
  secret_data = join("", [
    "postgresql+asyncpg://",
    data.terraform_remote_state.database.outputs.database_user,
    ":",
    data.terraform_remote_state.database.outputs.database_password,
    "@",
    data.terraform_remote_state.database.outputs.private_ip_address,
    ":5432/",
    data.terraform_remote_state.database.outputs.database_name,
  ])
}
