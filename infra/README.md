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
└── compute/    # L7 — Cloud Run (frontend, api, worker) + Cloud Tasks
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

## À venir

- **M5** ajoutera `terraform plan` obligatoire en CI sur toute PR touchant
  `infra/`, et `apply` uniquement depuis `main` après review humaine.
- **L6** ajoutera les service accounts dédiés par service Cloud Run
  (permissions minimales, cf. agents.md §7).
