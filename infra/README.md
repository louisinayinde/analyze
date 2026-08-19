# Infra GCP (Terraform)

Référence : [backlog.md](../backlog.md) EPIC L (L1–L8) · [projets.md](../projets.md) §infra.

## Projet & état distant

| | |
|---|---|
| Projet GCP | `analyze-app-prod` |
| Région par défaut | `europe-west1` (Belgique — moins chère en Europe, RGPD) |
| Bucket d'état | `gs://analyze-app-prod-tfstate` |

Le bucket a été créé une fois via [`bootstrap.sh`](bootstrap.sh) (voir ce script pour le
détail et pour le reconstruire en cas de perte). Terraform ne gère pas ce bucket
lui-même : il ne peut pas stocker son propre état avant que l'état existe
(problème de l'œuf et de la poule), donc cette seule brique passe par `gcloud`.

**Verrouillage** : le backend `gcs` de Terraform verrouille nativement via un
objet de lock dans le bucket (écriture conditionnelle), sans ressource
supplémentaire à provisionner — contrairement à AWS où il faut une table
DynamoDB à côté du bucket S3.

## Structure

Un dossier par module, un **état Terraform séparé par module** (préfixe dédié
dans le même bucket) :

```
infra/
├── network/    # L2 — VPC + connecteur Cloud SQL
├── database/   # L3 — Cloud SQL Postgres
├── storage/    # L4 — bucket GCS images + Cloud CDN
├── secrets/    # L5 — Secret Manager
├── iam/        # L6 — service accounts par service Cloud Run
├── compute/    # L7 — Cloud Run (frontend, api, worker) + Cloud Tasks
└── armor/      # L8 — Cloud Armor (WAF + rate limiting en périphérie) devant api
```

Chaque module est un **root module Terraform indépendant** (son propre
`terraform init`/`plan`/`apply`), pas un module réutilisable appelé depuis une
racine commune. Pourquoi : ça respecte l'ordre de dépendance du backlog
(L2→L3, L1→L4, L1→L5→L6→(L3,L4,L6)→L7) sans forcer un apply global à chaque
changement, et ça limite le blast radius d'une erreur — un mauvais plan sur
`storage` ne touche pas l'état de `network`. C'est la même logique que la
modularité en dur dans le code (agents.md §4) appliquée à l'infra.

Chaque dossier contient pour l'instant seulement le squelette (`backend.tf`,
`versions.tf`, `variables.tf`, `providers.tf`) — les ressources sont ajoutées
ticket par ticket (L2 à L7). Pas de `main.tf` vide en attendant : on l'ajoute
quand il y a quelque chose dedans.

## Convention par module

- `backend.tf` : backend `gcs`, bucket `analyze-app-prod-tfstate`, `prefix`
  = nom du dossier (ex. `network`).
- `versions.tf` : `required_version >= 1.15`, provider `google ~> 7.0`.
- `variables.tf` : `project_id` (défaut `analyze-app-prod`) et `region`
  (défaut `europe-west1`) — un seul environnement pour l'instant (produit
  portfolio, un seul dev, cf. agents.md §2 sur le budget) ; pas de
  workspaces/environnements multiples tant qu'il n'y a pas de besoin réel.
- `providers.tf` : provider `google` câblé sur ces deux variables.

## Utilisation

```bash
cd infra/<module>
terraform init      # première fois, ou après modif de backend.tf
terraform plan
terraform apply
```

Prérequis local : Application Default Credentials configurées

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project analyze-app-prod
```

(La CI utilisera Workload Identity Federation à la place — M3, pas de clé de
service account statique.)

## Référencer les outputs d'un autre module

Chaque module ayant son propre état (voir plus haut), un module qui dépend
d'un autre lit ses outputs via `terraform_remote_state` plutôt que de
redupliquer des valeurs en dur. Exemple pour consommer le VPC créé par
`network` (L2) depuis `database` (L3) ou `compute` (L7) :

```hcl
data "terraform_remote_state" "network" {
  backend = "gcs"
  config = {
    bucket = "analyze-app-prod-tfstate"
    prefix = "network"
  }
}

# usage : data.terraform_remote_state.network.outputs.network_id
```

## Module compute (L7)

Services Cloud Run `frontend`/`api`/`worker` + queue Cloud Tasks + dépôt
Artifact Registry. Branche les service accounts du module `iam` (L6) sur
chaque service et bascule automatiquement les adaptateurs F1
(`FileJobsCloudTasks`)/E5 (`StockageImageGCS`) côté backend, qui n'attendaient
que ces variables d'environnement (`composition/adapters.py`,
`composition/app.py`) — aucun changement de code applicatif requis par ce
module.

Deux subtilités à connaître avant d'`apply` :

- **Images placeholder.** M2 (build & push Docker) n'existe pas encore : les
  trois services démarrent avec l'image publique
  `us-docker.pkg.dev/cloudrun/container/hello` (`variables.tf`). Chaque
  service porte un `lifecycle.ignore_changes` sur son image pour que
  Terraform ne revienne jamais sur le vrai déploiement que M2/M4 poussera
  plus tard hors Terraform.
- **CORS en deux temps.** `api` a besoin de l'URL de `frontend` pour
  restreindre `CORS_ORIGINS`, `frontend` a besoin de l'URL de `api` pour
  l'appeler — un vrai cycle si les deux se référençaient l'un l'autre.
  Premier `apply` : `frontend_url` reste vide (`CORS_ORIGINS=""`, défaut
  fermé). Relever l'URL avec `terraform output frontend_url`, puis refaire
  `terraform apply -var frontend_url=<url>` pour ouvrir le CORS côté `api`.

## Module armor (L8)

Cloud Armor **ne s'attache pas directement à Cloud Run** : il faut un Load
Balancer HTTPS externe (NEG serverless + backend service), sinon la policy
serait trivialement contournable en appelant l'URL `*.run.app` directement.
Scope volontairement limité à `api` (pas `frontend`) : c'est le seul service
dont un abus coûte réellement cher (appels LLM en aval via le worker) —
right-sizing, agents.md §2.

Composants : `google_compute_security_policy` (règles préconfigurées
`sqli-v33-stable` + `xss-v33-stable`, et une règle `rate_based_ban` qui
throttle à 120 req/min/IP puis bannit 10 min au-delà de 300 req/5 min —
complémentaire au rate limiting applicatif G, pas redondant : celui-ci coupe
le flood brut avant même d'atteindre Cloud Run) ; NEG serverless + backend
service portant la policy ; IP statique globale ; certificat Google-managed
sur un domaine [nip.io](https://nip.io) (DNS public gratuit qui résout
`<ip-avec-tirets>.nip.io` vers cette IP — évite d'acheter un domaine pour un
produit portfolio, agents.md §2) ; redirection HTTP → HTTPS.

**Séquence d'apply — deux temps, comme `frontend_url` (module compute)** :
le module `armor` a besoin que le service `api` existe déjà (son NEG pointe
dessus par nom), donc `armor` dépend de `compute`, jamais l'inverse. Mais une
fois le LB en place, il faut fermer l'accès direct `*.run.app` à `api` (sinon
Cloud Armor est contournable) et faire pointer le frontend sur l'URL du LB —
ce qui dépend en retour d'une sortie d'`armor`. Un vrai cycle, résolu en deux
applys distincts plutôt qu'un contournement fragile :

```bash
# 1. Une fois compute (L7) déployé, appliquer armor :
cd infra/armor
terraform init && terraform apply

# 2. Relever l'URL du LB, puis rouvrir compute dessus et fermer l'accès direct :
terraform output api_lb_url
cd ../compute
terraform apply -var api_public_url=<valeur de api_lb_url> -var restrict_api_ingress=true
```

Avant l'étape 2, `compute` garde son comportement L7 d'origine (accès direct
`*.run.app`, `NEXT_PUBLIC_API_URL` = URI Cloud Run) — aucune régression tant
que cette bascule n'est pas faite explicitement.

Le certificat Google-managed prend jusqu'à ~15-60 min pour passer `ACTIVE`
après le premier `apply` (validation asynchrone côté Google, pas un blocage
Terraform) : normal de voir `PROVISIONING` juste après.

## À venir

- **M5** ajoutera `terraform plan` obligatoire en CI sur toute PR touchant
  `infra/`, et `apply` uniquement depuis `main` après review humaine.
- **O3** validera en conditions réelles que G (applicatif) et L8 (Cloud
  Armor) se déclenchent tous les deux comme attendu.
