#!/usr/bin/env bash
# Bootstrap ponctuel de l'infra GCP : projet dédié + bucket d'état Terraform.
#
# À lancer une seule fois (ou pour reconstruire le bootstrap si le projet est
# perdu/recréé). Ce script existe car Terraform ne peut pas gérer lui-même le
# bucket qui stocke SON PROPRE état (problème de l'œuf et de la poule) : on
# passe par gcloud pour cette seule brique, puis tous les modules infra/*
# utilisent ce bucket comme backend distant.
#
# Prérequis : gcloud CLI authentifié (gcloud auth login) sur un compte ayant
# le droit de créer des projets sur l'organisation/compte de facturation.
set -euo pipefail

PROJECT_ID="analyze-app-prod"
PROJECT_NAME="Analyze"
REGION="europe-west1"
STATE_BUCKET="${PROJECT_ID}-tfstate"

# Compte de facturation à lier. Ajuste si besoin :
#   gcloud billing accounts list
BILLING_ACCOUNT_ID="01D17C-14CE60-06F1F1"

echo "== Projet GCP =="
if gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then
  echo "Projet $PROJECT_ID déjà existant, on continue."
else
  gcloud projects create "$PROJECT_ID" --name="$PROJECT_NAME"
fi

echo "== Facturation =="
gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT_ID"

echo "== APIs =="
gcloud services enable storage.googleapis.com --project="$PROJECT_ID"

echo "== Bucket d'état Terraform =="
if gcloud storage buckets describe "gs://${STATE_BUCKET}" >/dev/null 2>&1; then
  echo "Bucket gs://${STATE_BUCKET} déjà existant, on continue."
else
  gcloud storage buckets create "gs://${STATE_BUCKET}" \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --uniform-bucket-level-access \
    --public-access-prevention
fi

# Versioning : permet de restaurer un état précédent en cas de corruption ou
# d'apply erroné (rollback manuel via `gcloud storage objects` + `terraform
# state push`).
gcloud storage buckets update "gs://${STATE_BUCKET}" --versioning

# Lifecycle : sans ça, le versioning garde indéfiniment TOUTES les révisions
# d'état, y compris celles générées par chaque plan/apply en CI (M5). Coût
# négligeable vu la taille des fichiers d'état, mais autant borner : on garde
# au minimum 15 versions, et on ne supprime une version non-courante qu'après
# 30 jours sans y toucher.
LIFECYCLE_FILE="$(mktemp)"
trap 'rm -f "$LIFECYCLE_FILE"' EXIT
cat > "$LIFECYCLE_FILE" << 'EOF'
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {
        "numNewerVersions": 15,
        "daysSinceNoncurrentTime": 30
      }
    }
  ]
}
EOF
gcloud storage buckets update "gs://${STATE_BUCKET}" --lifecycle-file="$LIFECYCLE_FILE"

echo "== Terraform : Application Default Credentials =="
echo "Si 'terraform init' échoue avec 'could not find default credentials', lancer :"
echo "  gcloud auth application-default login"
echo "  gcloud auth application-default set-quota-project ${PROJECT_ID}"

echo "== Terminé =="
echo "Bucket d'état : gs://${STATE_BUCKET}"
echo "Prochaine étape : dans chaque infra/<module>/, lancer 'terraform init'."
