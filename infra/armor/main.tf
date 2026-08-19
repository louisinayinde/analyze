# Pas de google_project_service ici : Cloud Armor, les NEG serverless et le
# Load Balancer externe font tous partie de l'API compute.googleapis.com,
# déjà activée par le module network (L2). Même logique que compute/main.tf
# qui n'active pas non plus vpcaccess.googleapis.com pour autant qu'il
# l'utilise (agents.md §1 DRY — une API, activée une seule fois, là où le
# besoin apparaît en premier).

# --- Policy Cloud Armor : WAF + rate limiting en périphérie ---
# Volontairement minimale (agents.md §1 KISS, §2 budget) : les deux jeux de
# règles préconfigurées les plus consensuels pour une API JSON (pas les ~15
# disponibles — plus de règles = plus de faux positifs à trier, sans gain de
# sécurité proportionnel ici) + une seule règle de rate limiting qui combine
# throttle et ban (voir plus bas).
#
# Adaptive Protection (détection DDoS L7 par ML) est volontairement absente :
# nécessite Cloud Armor Managed Protection Plus, un abonnement à coût fixe
# mensuel élevé, hors de proportion pour un produit portfolio à faible
# trafic. À reconsidérer si le trafic réel le justifie un jour (O4, ADRs
# différés, backlog.md).
resource "google_compute_security_policy" "api" {
  name        = "analyze-api-armor"
  project     = var.project_id
  description = "WAF + rate limiting en périphérie pour le service api (L8), en complément du rate limiting applicatif (G, backlog.md)."
  type        = "CLOUD_ARMOR"

  # Règle par défaut explicite (GCP en crée toujours une à cette priorité ;
  # la déclarer évite un diff Terraform permanent). Le filtrage réel se fait
  # dans les règles de priorité inférieure ci-dessous, évaluées avant.
  rule {
    action   = "allow"
    priority = "2147483647"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    description = "Règle par défaut : autoriser."
  }

  rule {
    action   = "deny(403)"
    priority = "1000"
    match {
      expr {
        expression = "evaluatePreconfiguredExpr('sqli-v33-stable')"
      }
    }
    description = "Bloque les tentatives d'injection SQL détectées par le jeu de règles préconfiguré."
  }

  rule {
    action   = "deny(403)"
    priority = "1001"
    match {
      expr {
        expression = "evaluatePreconfiguredExpr('xss-v33-stable')"
      }
    }
    description = "Bloque les tentatives XSS détectées par le jeu de règles préconfiguré."
  }

  # Rate limiting par IP, en amont de Cloud Run. Complémentaire au rate
  # limiting applicatif (G) : celui-ci vit dans une table Postgres et
  # applique un quota fin par IP/user_id sur POST /analyses (coût métier,
  # après authentification) ; celui-ci coupe le flood brut/scraping/bots
  # avant même que la requête n'atteigne Cloud Run (coût infra). Une seule
  # règle `rate_based_ban` plutôt que deux règles séparées (throttle + ban) :
  # deux règles matchant toutes les deux "*" à des priorités différentes ne
  # s'empileraient pas — Cloud Armor s'arrête à la première règle qui
  # matche, donc la seconde ne serait jamais évaluée. `rate_based_ban` gère
  # les deux paliers dans une seule règle (seuil normal -> 429, seuil
  # persistant -> ban temporaire).
  rule {
    action   = "rate_based_ban"
    priority = "2000"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"

      rate_limit_threshold {
        count        = 120
        interval_sec = 60
      }

      ban_duration_sec = 600
      ban_threshold {
        count        = 300
        interval_sec = 300
      }
    }
    description = "Throttle 120 req/min/IP (429 au-delà) ; ban 10 min pour une IP qui dépasse 300 req/5 min de façon soutenue."
  }
}

# --- NEG serverless : pont entre le LB et le service Cloud Run api ---
# "api" est le nom littéral du service (google_cloud_run_v2_service.api.name,
# module compute) : un contrat stable entre les deux modules, comme les
# account_id littéraux du module iam (ex. "cloudrun-api"). Pas besoin de le
# lire via terraform_remote_state pour autant — c'est juste une chaîne, pas
# une valeur calculée.
resource "google_compute_region_network_endpoint_group" "api" {
  name                  = "analyze-api-neg"
  project               = var.project_id
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = "api"
  }
}

# --- Backend service : c'est ici que la policy Cloud Armor s'attache ---
# protocol = "HTTP" : valeur attendue par Google pour un backend serverless
# NEG (le chiffrement GFE -> Cloud Run est géré automatiquement par la
# plateforme, indépendamment de ce champ). Pas de health_checks : non
# supporté/non pertinent pour un backend serverless, Cloud Run gère sa
# propre santé.
resource "google_compute_backend_service" "api" {
  name    = "analyze-api-backend"
  project = var.project_id

  load_balancing_scheme = "EXTERNAL_MANAGED"
  protocol              = "HTTP"
  port_name             = "http"
  timeout_sec           = 30

  security_policy = google_compute_security_policy.api.id

  backend {
    group = google_compute_region_network_endpoint_group.api.id
  }

  # Logs de requête activés : seul moyen d'observer les 403/429 émis par la
  # policy ci-dessus (agents.md §9, observabilité). Sample_rate à 1.0 : coût
  # marginal négligeable au volume de ce produit.
  log_config {
    enable      = true
    sample_rate = 1.0
  }
}

# --- IP statique globale + domaine nip.io ---
# nip.io est un service DNS public gratuit qui résout <ip-avec-tirets>.nip.io
# vers <ip>, sans configuration ni achat de domaine. Ça permet d'obtenir un
# certificat Google-managed (qui exige un nom de domaine résolvable) sans
# dépense ni domaine réel — solution pragmatique pour un produit portfolio à
# budget serré (agents.md §2), documentée comme telle plutôt que cachée.
# La chaîne se construit à partir de l'IP réservée ci-dessous, donc tout se
# résout dans le même apply (contrairement au frontend_url du module compute,
# qui lui a un vrai cycle de dépendance à casser en deux applys).
resource "google_compute_global_address" "api_lb" {
  name    = "analyze-api-lb-ip"
  project = var.project_id
}

locals {
  api_lb_domain = "${replace(google_compute_global_address.api_lb.address, ".", "-")}.nip.io"
}

resource "google_compute_managed_ssl_certificate" "api" {
  name    = "analyze-api-lb-cert"
  project = var.project_id

  managed {
    domains = [local.api_lb_domain]
  }
}

# --- HTTPS : le chemin réel du trafic ---
resource "google_compute_url_map" "api" {
  name            = "analyze-api-lb-url-map"
  project         = var.project_id
  default_service = google_compute_backend_service.api.id
}

resource "google_compute_target_https_proxy" "api" {
  name             = "analyze-api-lb-https-proxy"
  project          = var.project_id
  url_map          = google_compute_url_map.api.id
  ssl_certificates = [google_compute_managed_ssl_certificate.api.id]
}

resource "google_compute_global_forwarding_rule" "api_https" {
  name                  = "analyze-api-lb-https"
  project               = var.project_id
  ip_address            = google_compute_global_address.api_lb.address
  port_range            = "443"
  target                = google_compute_target_https_proxy.api.id
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# --- HTTP : redirection systématique vers HTTPS ---
# Réutilise la même IP globale (un seul forwarding rule par port, pas de
# deuxième adresse à payer). Sans ce couple proxy/forwarding rule, un client
# qui tape http:// verrait une erreur de connexion plutôt qu'une redirection
# propre.
resource "google_compute_url_map" "api_http_redirect" {
  name    = "analyze-api-lb-http-redirect"
  project = var.project_id

  default_url_redirect {
    https_redirect = true
    strip_query    = false
  }
}

resource "google_compute_target_http_proxy" "api" {
  name    = "analyze-api-lb-http-proxy"
  project = var.project_id
  url_map = google_compute_url_map.api_http_redirect.id
}

resource "google_compute_global_forwarding_rule" "api_http" {
  name                  = "analyze-api-lb-http"
  project               = var.project_id
  ip_address            = google_compute_global_address.api_lb.address
  port_range            = "80"
  target                = google_compute_target_http_proxy.api.id
  load_balancing_scheme = "EXTERNAL_MANAGED"
}
