# API nécessaire pour créer des service accounts. Activée ici (pas dans
# bootstrap.sh) : spécifique à ce module, même logique que sqladmin dans
# database/main.tf et secretmanager dans secrets/main.tf.
resource "google_project_service" "iam" {
  project = var.project_id
  service = "iam.googleapis.com"

  disable_on_destroy = false
}

# État du module secrets (L5) : lecture des IDs de secret plutôt que de les
# redupliquer en dur (agents.md §1 DRY, même convention que database/main.tf
# lisant l'état de network).
data "terraform_remote_state" "secrets" {
  backend = "gcs"
  config = {
    bucket = "analyze-app-prod-tfstate"
    prefix = "secrets"
  }
}

# État du module storage (L4) : lecture du nom du bucket d'images pour
# n'accorder l'écriture qu'au service qui en a réellement besoin.
data "terraform_remote_state" "storage" {
  backend = "gcs"
  config = {
    bucket = "analyze-app-prod-tfstate"
    prefix = "storage"
  }
}

# --- Service accounts dédiés, un par service Cloud Run (L7) ---
# Un SA par service, jamais un SA partagé : c'est la seule façon d'accorder
# des permissions différenciées (agents.md §7, moindre privilège). Un SA
# unique aurait l'union de tous les accès et annulerait la promesse du
# ticket (frontend sans accès DB/secrets).
resource "google_service_account" "frontend" {
  project      = var.project_id
  account_id   = "cloudrun-frontend"
  display_name = "Cloud Run - frontend"

  depends_on = [google_project_service.iam]
}

resource "google_service_account" "api" {
  project      = var.project_id
  account_id   = "cloudrun-api"
  display_name = "Cloud Run - api"

  depends_on = [google_project_service.iam]
}

resource "google_service_account" "worker" {
  project      = var.project_id
  account_id   = "cloudrun-worker"
  display_name = "Cloud Run - worker"

  depends_on = [google_project_service.iam]
}

# --- Accès aux secrets (L5), au cas par cas ---
# La connexion DB se fait par IP privée + mot de passe, jamais par IAM DB
# Authentication ni Cloud SQL Auth Proxy (database/main.tf) : il n'existe
# donc pas de rôle Cloud SQL séparé à accorder. Le secret database-url EST le
# seul channel d'accès à la DB — "accès DB" se traduit entièrement par
# secretAccessor sur ce secret précis.

# api : lit database-url (requêtes cache/historique, D/H) et jwt-signing-key
# (émission/vérification des JWT, C4/C6/C7). Jamais llm-api-key : l'api
# n'appelle jamais le LLM directement (F4, backlog.md — seul le worker le
# fait, en asynchrone).
resource "google_secret_manager_secret_iam_member" "api_database_url" {
  project   = var.project_id
  secret_id = data.terraform_remote_state.secrets.outputs.database_url_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "api_jwt_signing_key" {
  project   = var.project_id
  secret_id = data.terraform_remote_state.secrets.outputs.jwt_signing_key_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

# worker : lit database-url (met à jour status/hit_count, F2) et llm-api-key
# (seul service qui appelle le fournisseur IA, E1/F2). Pas d'accès à
# jwt-signing-key : le worker ne fait aucune vérification d'authentification
# applicative (F3 utilise un token OIDC Cloud Tasks, pas ce secret).
resource "google_secret_manager_secret_iam_member" "worker_database_url" {
  project   = var.project_id
  secret_id = data.terraform_remote_state.secrets.outputs.database_url_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_secret_manager_secret_iam_member" "worker_llm_api_key" {
  project   = var.project_id
  secret_id = data.terraform_remote_state.secrets.outputs.llm_api_key_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.worker.email}"
}

# frontend : volontairement aucun binding de secret ci-dessus (exigence
# explicite du ticket L6). Le frontend Next.js sert des pages et appelle
# l'api en HTTP — il n'a besoin d'aucun credential DB ni LLM. S'il était
# compromis (XSS, dépendance vérolée...), il n'hériterait d'aucun de ces
# accès.

# --- Bucket images (L4) : écriture réservée au worker ---
# objectCreator plutôt qu'objectAdmin : le worker crée des objets neufs
# (images générées, jamais réécrites ni supprimées — storage/main.tf) mais
# n'a jamais besoin de les lister, lire en dehors du public, ni les
# supprimer/écraser (agents.md §7, moindre privilège). La lecture publique
# est déjà couverte par google_storage_bucket_iam_member.images_public_read
# (L4, allUsers) — aucun besoin de droit de lecture supplémentaire ici.
resource "google_storage_bucket_iam_member" "worker_images_write" {
  bucket = data.terraform_remote_state.storage.outputs.images_bucket_name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.worker.email}"
}
