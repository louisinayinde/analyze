#!/usr/bin/env bash
# H2 (backlog.md) : régénère front/shared/api/schema.gen.ts à partir du
# schéma OpenAPI réellement exposé par le backend (agents.md §3 — le
# contrat est la source de vérité, pas le code). À relancer après tout
# changement de route/schéma back, puis committer le fichier généré.
#
# La CI (.github/workflows/ci.yml) rejoue ce même script et échoue si le
# fichier committé a dérivé du schéma backend — ce script est donc la seule
# façon supportée de le régénérer, en local comme en CI.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

schema_tmp="$(mktemp -t openapi-schema.XXXXXX.json)"
trap 'rm -f "$schema_tmp"' EXIT

(cd "$repo_root/back" && uv run python src/export_openapi.py) >"$schema_tmp"

(cd "$repo_root/front" && npx --no-install openapi-typescript "$schema_tmp" -o shared/api/schema.gen.ts)

echo "Client TS régénéré : front/shared/api/schema.gen.ts"
