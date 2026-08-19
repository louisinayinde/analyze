# APIs nécessaires à ce module. Activées ici (pas ailleurs) : spécifiques au
# compute, même logique que sqladmin (database), secretmanager (secrets),
# iam (iam).
resource "google_project_service" "run" {
  project = var.project_id
  service = "run.googleapis.com"

  disable_on_destroy = false
}

resource "google_project_service" "cloudtasks" {
  project = var.project_id
  service = "cloudtasks.googleapis.com"

  disable_on_destroy = false
}

resource "google_project_service" "artifactregistry" {
  project = var.project_id
  service = "artifactregistry.googleapis.com"

  disable_on_destroy = false
}

# États des modules dont ce module dépend (L3, L4, L6 — backlog.md), lus
# plutôt que redupliqués en dur (agents.md §1 DRY, même convention que
# database/main.tf lisant network, ou iam/main.tf lisant secrets/storage).
# L2 (network) est lu directement ici, pas seulement via L3 : `api` et
# `worker` ont besoin du connecteur VPC pour joindre Cloud SQL en IP
# privée, exactement comme l'API elle-même en dev via le connecteur créé
# par L2.
data "terraform_remote_state" "network" {
  backend = "gcs"
  config = {
    bucket = "analyze-app-prod-tfstate"
    prefix = "network"
  }
}

data "terraform_remote_state" "storage" {
  backend = "gcs"
  config = {
    bucket = "analyze-app-prod-tfstate"
    prefix = "storage"
  }
}

data "terraform_remote_state" "secrets" {
  backend = "gcs"
  config = {
    bucket = "analyze-app-prod-tfstate"
    prefix = "secrets"
  }
}

data "terraform_remote_state" "iam" {
  backend = "gcs"
  config = {
    bucket = "analyze-app-prod-tfstate"
    prefix = "iam"
  }
}

# Dépôt Artifact Registry des images Docker (projets.md §infra). Créé ici
# (pas dans un module dédié) : `compute` est le seul consommateur de ces
# images, et le backlog n'a jamais prévu de ticket infra séparé pour cette
# brique — un module de plus pour une seule ressource irait contre KISS
# (agents.md §1, §2). M2 (backlog.md) poussera les images `frontend`/
# `api`/`worker` ici ; jusque-là les services ci-dessous utilisent l'image
# placeholder (variables.tf).
resource "google_artifact_registry_repository" "images" {
  project       = var.project_id
  location      = var.region
  repository_id = "analyze-app"
  format        = "DOCKER"
  description   = "Images Docker frontend/api/worker (M2, backlog.md)."

  depends_on = [google_project_service.artifactregistry]
}

# File de jobs de génération asynchrone (F1/F3, projets.md). Débit
# volontairement modeste : ce produit n'a pas de trafic à absorber en
# masse, un débit élevé par défaut ne ferait qu'exposer le budget LLM à un
# pic non maîtrisé si la file se remplissait d'un coup (agents.md §2).
# Retries avec backoff exponentiel (agents.md §3) : la tâche transporte le
# texte source (F1, cf. docstring de FileJobsCloudTasks), donc rejouable
# sans perte si `worker` échoue transitoirement.
resource "google_cloud_tasks_queue" "jobs" {
  name     = "analyse-jobs"
  project  = var.project_id
  location = var.region

  rate_limits {
    max_dispatches_per_second = 5
    max_concurrent_dispatches = 5
  }

  retry_config {
    max_attempts = 5
    min_backoff  = "10s"
    max_backoff  = "300s"
  }

  depends_on = [google_project_service.cloudtasks]
}

# URL publique effective de api pour le frontend (voir variables.tf,
# api_public_url) : soit l'URI Cloud Run directe (par défaut, comportement
# actuel), soit l'URL du Load Balancer Cloud Armor une fois L8 appliqué.
locals {
  api_public_url = var.api_public_url != "" ? var.api_public_url : google_cloud_run_v2_service.api.uri
}

# --- Service worker ---
# Créé en premier des trois : `api` a besoin de son URL (WORKER_INTERNAL_URL,
# F1) et `frontend` n'en a jamais besoin (le worker n'est jamais appelé par
# le navigateur, projets.md). Aucune dépendance vers les deux autres
# services : casse le cycle décrit dans variables.tf pour `frontend_url`.
resource "google_cloud_run_v2_service" "worker" {
  name     = "worker"
  project  = var.project_id
  location = var.region

  # Service stateless, recréable depuis Terraform à tout moment (aucune
  # donnée n'y vit) — contrairement à `deletion_protection = true` sur
  # l'instance Cloud SQL (database/main.tf) où c'est la donnée elle-même
  # qu'on protège (agents.md §13, priorité 1). Rien d'équivalent ici.
  deletion_protection = false

  template {
    service_account = data.terraform_remote_state.iam.outputs.worker_service_account_email

    # Scale-to-zero (budget serré, agents.md §2) : ce produit portfolio n'a
    # pas de trafic constant à absorber, payer une instance idle 24/7 pour
    # un worker qui ne traite des jobs que par intermittence serait le
    # genre de dépense que agents.md §2 proscrit explicitement. Plafond bas
    # : un seul dev, pas de pic multi-tenant à couvrir.
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    # Connecteur VPC serverless (L2) : seul moyen pour ce processus
    # d'atteindre la base en IP privée (D2/F2, `CachePort.marquer_termine`/
    # `marquer_echec`). PRIVATE_RANGES_ONLY plutôt que ALL_TRAFFIC : les
    # appels sortants vers le fournisseur LLM (E1) restent sur l'internet
    # public directement, sans passer par le connecteur payant pour rien
    # (agents.md §2, §8).
    vpc_access {
      connector = data.terraform_remote_state.network.outputs.vpc_access_connector_id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = var.container_image_worker

      # Port 8000 : aligné sur `back/Dockerfile.dev`
      # (`uvicorn ... --port 8000`), convention reprise par le futur
      # Dockerfile de prod (M2) — pas de raison de diverger.
      ports {
        container_port = 8000
      }

      # Le tier le plus bas qui tient la charge actuelle (agents.md §2,
      # right-sizing) ; à ajuster si les métriques (N2) montrent une
      # saturation réelle, jamais par anticipation.
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = data.terraform_remote_state.secrets.outputs.database_url_secret_id
            version = "latest"
          }
        }
      }

      # `Settings.postgres_user/password/db` (shared/config.py) sont
      # requis (pas de défaut) mais ne sont lus par aucun code en dehors de
      # leur propre déclaration — servent uniquement au service `postgres`
      # du docker-compose local. Dette pré-existante hors scope de ce
      # ticket infra (L7 ne touche pas au code Python) : valeurs factices
      # ici, seulement pour satisfaire la validation Pydantic au démarrage.
      # À nettoyer un jour côté back (leur donner un défaut vide).
      env {
        name  = "POSTGRES_USER"
        value = "unused-in-prod"
      }
      env {
        name  = "POSTGRES_PASSWORD"
        value = "unused-in-prod"
      }
      env {
        name  = "POSTGRES_DB"
        value = "unused-in-prod"
      }

      env {
        name = "LLM_API_KEY"
        value_source {
          secret_key_ref {
            secret  = data.terraform_remote_state.secrets.outputs.llm_api_key_secret_id
            version = "latest"
          }
        }
      }

      # Bucket GCS (L4) : renseigné -> `StockageImageGCS` câblé à la place
      # de l'adaptateur filesystem (E5, composition/adapters.py), sans
      # aucun changement de code.
      env {
        name  = "GCS_BUCKET_IMAGES"
        value = data.terraform_remote_state.storage.outputs.images_bucket_name
      }
    }
  }

  # M2/M4 (backlog.md) déploieront la vraie image hors Terraform (`gcloud
  # run deploy` ou équivalent CI) ; sans ce `ignore_changes`, le prochain
  # `terraform apply` de ce module reviendrait sur le placeholder et
  # écraserait un déploiement applicatif valide (même logique que
  # `frontend_url` ci-dessus : deux ordres de bataille — Terraform pour
  # l'existence du service, CI/CD pour son contenu — qui ne doivent pas se
  # marcher dessus).
  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }

  depends_on = [google_project_service.run]
}

# Seul `worker` (via son propre service account, utilisé par
# `FileJobsCloudTasks` pour signer le jeton OIDC — composition/app.py,
# `WORKER_SERVICE_ACCOUNT_EMAIL`) a le droit d'invoquer ce service.
# Ni `allUsers` ni aucun autre compte : c'est la première couche de défense
# en profondeur (IAM), la seconde étant la vérification applicative du
# jeton OIDC dans `api_worker.verifier_origine_cloud_tasks` (F3, agents.md
# §7 — sécurité non négociable même sur un endpoint interne).
resource "google_cloud_run_v2_service_iam_member" "worker_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.worker.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${data.terraform_remote_state.iam.outputs.worker_service_account_email}"
}

# `api` crée les tâches Cloud Tasks (FileJobsCloudTasks._creer_tache) en
# signant leur jeton OIDC comme le compte de service `worker` (pas le
# sien) : c'est ce SA-là que `verifier_origine_cloud_tasks` (F3) attend.
# Minter un jeton "en tant que" un autre SA exige `iam.serviceAccounts.actAs`
# sur ce SA cible (roles/iam.serviceAccountUser) — sans ce binding, la
# création de la tâche échouerait côté API Cloud Tasks (permission denied),
# jamais silencieusement.
resource "google_service_account_iam_member" "api_actas_worker" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${data.terraform_remote_state.iam.outputs.worker_service_account_email}"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${data.terraform_remote_state.iam.outputs.api_service_account_email}"
}

# `api` doit pouvoir enfiler des tâches sur cette queue précise (moindre
# privilège, agents.md §7 — pas roles/cloudtasks.admin, juste le droit
# d'enfiler).
resource "google_cloud_tasks_queue_iam_member" "api_enqueuer" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_tasks_queue.jobs.name
  role     = "roles/cloudtasks.enqueuer"
  member   = "serviceAccount:${data.terraform_remote_state.iam.outputs.api_service_account_email}"
}

# --- Service api ---
# Dépend réellement de `worker` (son URL, WORKER_INTERNAL_URL) et de la
# queue ci-dessus ; dépend seulement de la *variable* `frontend_url` pour
# CORS, jamais de la ressource `frontend` elle-même (casse le cycle décrit
# dans variables.tf).
resource "google_cloud_run_v2_service" "api" {
  name     = "api"
  project  = var.project_id
  location = var.region

  deletion_protection = false # même raisonnement que le service worker ci-dessus

  # Par défaut INGRESS_TRAFFIC_ALL (accès direct *.run.app, comportement
  # actuel de L7). Une fois restrict_api_ingress=true (après apply de L8,
  # voir variables.tf), seul le trafic interne au VPC ou passant par un Load
  # Balancer Cloud Run est accepté — ferme l'accès direct pour que la policy
  # Cloud Armor du module armor ne soit pas contournable.
  ingress = var.restrict_api_ingress ? "INGRESS_TRAFFIC_INTERNAL_AND_CLOUD_LOAD_BALANCING" : "INGRESS_TRAFFIC_ALL"

  template {
    service_account = data.terraform_remote_state.iam.outputs.api_service_account_email

    # Plafond un peu plus haut que worker : `api` sert les requêtes
    # synchrones du navigateur (latence perçue directement par
    # l'utilisateur), `worker` traite en tâche de fond (projets.md). Reste
    # scale-to-zero : même budget serré qu'ailleurs (agents.md §2).
    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    vpc_access {
      connector = data.terraform_remote_state.network.outputs.vpc_access_connector_id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = var.container_image_api

      ports {
        container_port = 8000
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = data.terraform_remote_state.secrets.outputs.database_url_secret_id
            version = "latest"
          }
        }
      }

      # Voir le commentaire équivalent sur le service worker ci-dessus :
      # champs requis par Settings mais non lus en prod.
      env {
        name  = "POSTGRES_USER"
        value = "unused-in-prod"
      }
      env {
        name  = "POSTGRES_PASSWORD"
        value = "unused-in-prod"
      }
      env {
        name  = "POSTGRES_DB"
        value = "unused-in-prod"
      }

      env {
        name = "JWT_SIGNING_KEY"
        value_source {
          secret_key_ref {
            secret  = data.terraform_remote_state.secrets.outputs.jwt_signing_key_secret_id
            version = "latest"
          }
        }
      }

      # Voir variables.tf : vide au premier apply (aucune origine
      # autorisée), à renseigner ensuite avec l'URL réelle de `frontend`.
      env {
        name  = "CORS_ORIGINS"
        value = var.frontend_url
      }

      env {
        name  = "GCS_BUCKET_IMAGES"
        value = data.terraform_remote_state.storage.outputs.images_bucket_name
      }

      # `FileJobsPort` (F1) -> `FileJobsCloudTasks` dès que
      # `CLOUD_TASKS_QUEUE` est renseignée (composition/app.py) : c'est
      # exactement la bascule que ce ticket doit produire.
      env {
        name  = "CLOUD_TASKS_QUEUE"
        value = google_cloud_tasks_queue.jobs.name
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "WORKER_INTERNAL_URL"
        value = "${google_cloud_run_v2_service.worker.uri}/internal/jobs/analyses"
      }
      env {
        name  = "WORKER_SERVICE_ACCOUNT_EMAIL"
        value = data.terraform_remote_state.iam.outputs.worker_service_account_email
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }

  depends_on = [google_project_service.run]
}

# Public : c'est l'endpoint que le navigateur (frontend) et
# NEXT_PUBLIC_API_URL appellent directement (K1-K6, projets.md).
# L'autorisation réelle reste appliquée par endpoint côté serveur (auth
# JWT, rate limiting G — agents.md §7, le client n'est jamais l'autorité) ;
# `allUsers` ici ne fait qu'autoriser le transport HTTP jusqu'à l'app.
resource "google_cloud_run_v2_service_iam_member" "api_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# --- Service frontend ---
# Dépend réellement de `api` (son URL, publique) — c'est ce sens de
# dépendance qui reste possible sans cycle (voir variables.tf).
resource "google_cloud_run_v2_service" "frontend" {
  name     = "frontend"
  project  = var.project_id
  location = var.region

  deletion_protection = false

  template {
    service_account = data.terraform_remote_state.iam.outputs.frontend_service_account_email

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    # Pas de `vpc_access` : le frontend ne parle qu'à `api` en HTTPS public
    # et ne touche jamais la base ni les secrets (L6 — aucun accès DB ni
    # secrets pour ce service account, exigence explicite du ticket L6).

    containers {
      image = var.container_image_frontend

      # Port 3000 : aligné sur `front/Dockerfile.dev` (`npm run dev`,
      # docker-compose.yml `"3000:3000"`) — même convention reprise par le
      # futur Dockerfile de prod (M2).
      ports {
        container_port = 3000
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      # local.api_public_url : URI Cloud Run directe tant que L8 (Cloud
      # Armor, module armor) n'a pas été appliqué, sinon l'URL du Load
      # Balancer (voir variables.tf, api_public_url). Même valeur pour les
      # deux : `api` étant public dans les deux cas (roles/run.invoker ->
      # allUsers ci-dessus, ou trafic LB), les Route Handlers Next.js (J3) et
      # le navigateur appellent la même URL — pas de load balancer/VPC
      # interne dédié séparé pour un usage strictement interne (budget,
      # agents.md §2).
      env {
        name  = "NEXT_PUBLIC_API_URL"
        value = local.api_public_url
      }
      env {
        name  = "API_INTERNAL_URL"
        value = local.api_public_url
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }

  depends_on = [google_project_service.run]
}

# Public : c'est l'entrée du produit pour un visiteur (K4 — page résultat
# publique partageable, projets.md).
resource "google_cloud_run_v2_service_iam_member" "frontend_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.frontend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
