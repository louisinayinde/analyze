# API nécessaire à ce module pour la backend bucket / load balancer Cloud CDN.
# Activée ici (pas dans network/L2) : L4 dépend seulement de L1 (infra/README.md,
# backlog.md), donc ce module doit pouvoir s'appliquer seul sans attendre L2.
# Réactivation idempotente si L2 l'a déjà fait — sans effet de bord.
resource "google_project_service" "compute" {
  project = var.project_id
  service = "compute.googleapis.com"

  disable_on_destroy = false
}

# Bucket des images générées. Contenu immuable une fois produit (projets.md) :
# pas de versioning (chaque analyse produit un objet distinct, jamais réécrit),
# pas de force_destroy (agents.md §13 — sûreté des données avant tout, un
# `terraform destroy` accidentel ne doit pas pouvoir vider le bucket).
resource "google_storage_bucket" "images" {
  name     = "${var.project_id}-images"
  project  = var.project_id
  location = var.region

  storage_class               = "STANDARD"
  uniform_bucket_level_access = true

  # Volontairement PAS de public_access_prevention ici (contrairement au
  # bucket d'état, cf. bootstrap.sh) : ces images sont faites pour être
  # partagées publiquement (projets.md — "visuel partageable"), la lecture
  # publique ci-dessous est voulue, pas une fuite.

  # "Tiering froid après 30 jours" (ticket L4) : Coldline plutôt que Nearline
  # car ce contenu est consulté surtout dans les jours suivant sa génération
  # (partage social) puis quasiment plus (agents.md §2 — le stockage a un
  # coût, Coldline coûte très significativement moins cher que Standard).
  # Durée minimale de stockage Coldline = 90 jours avant suppression/nouvelle
  # transition sans frais anticipés : sans impact ici puisque le contenu est
  # immuable et n'est jamais supprimé ni retransitionné.
  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }
}

# Lecture publique seule (agents.md §7 — moindre privilège) : aucune écriture
# publique. L'écriture reviendra au seul service account `worker` (module iam,
# L6), jamais au bucket lui-même en public.
resource "google_storage_bucket_iam_member" "images_public_read" {
  bucket = google_storage_bucket.images.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

# Backend bucket Cloud CDN : c'est la brique qui met le bucket GCS derrière
# un cache en périphérie plutôt que de servir chaque requête depuis l'origin.
resource "google_compute_backend_bucket" "images" {
  name        = "analyze-images-cdn"
  bucket_name = google_storage_bucket.images.name
  enable_cdn  = true

  # "Cache headers longs" (ticket L4) : FORCE_CACHE_ALL fait autorité côté CDN
  # indépendamment des en-têtes Cache-Control envoyés au moment de l'upload
  # par l'adaptateur StockageImagePort (E5) — un oubli côté appli ne dégrade
  # pas le cache. Justifié uniquement parce que le contenu est immuable
  # (projets.md) : un objet réécrit avec le même nom resterait caché à
  # l'ancienne valeur pendant toute la TTL, ce qui serait faux pour du contenu
  # mutable.
  cdn_policy {
    cache_mode       = "FORCE_CACHE_ALL"
    default_ttl      = 31536000 # 1 an
    max_ttl          = 31536000
    client_ttl       = 31536000
    negative_caching = true # les 404 restent brefs en cache, pas 1 an
  }

  depends_on = [google_project_service.compute]
}

resource "google_compute_url_map" "images" {
  name            = "analyze-images-lb"
  default_service = google_compute_backend_bucket.images.id
}

# HTTP seul pour l'instant, volontairement : un certificat managé Google
# exige un domaine dont on prouve la propriété via DNS, et ce projet n'en a
# aucun (aucune mention dans projets.md/backlog.md) — KISS/YAGNI (agents.md
# §2), on documente le chemin vers HTTPS plutôt que de le construire sans
# domaine réel à y accrocher.
#
# Point de vigilance à traiter avant L7 (compute) : le frontend Next.js sera
# servi en HTTPS (Cloud Run), et Chrome upgrade puis bloque le contenu mixte
# (image http:// chargée depuis une page https://) si l'upgrade échoue. Tant
# qu'aucun domaine n'est enregistré pour brancher un certificat managé sur ce
# load balancer, `<img src="http://...">` cassera silencieusement en prod.
resource "google_compute_target_http_proxy" "images" {
  name    = "analyze-images-http-proxy"
  url_map = google_compute_url_map.images.id
}

resource "google_compute_global_address" "images_lb_ip" {
  name = "analyze-images-lb-ip"
}

resource "google_compute_global_forwarding_rule" "images" {
  name                  = "analyze-images-lb-forwarding-rule"
  target                = google_compute_target_http_proxy.images.id
  ip_address            = google_compute_global_address.images_lb_ip.id
  port_range            = "80"
  load_balancing_scheme = "EXTERNAL"
}
