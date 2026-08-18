import json

from composition import create_app

# Point d'entrée pour H2 (backlog.md) : imprime le schéma OpenAPI sur
# stdout, à partir de l'app réellement montée (mêmes routes, tags et
# exemples que H1) — pas un document maintenu à la main en parallèle
# (agents.md §3 : le contrat est la source de vérité, pas le code).
#
# `create_app()` suffit : `app.openapi()` ne fait que construire le schéma
# depuis les routes montées, sans lifespan ni connexion Postgres réelle
# (voir tests/composition/test_openapi.py). `Settings` doit tout de même
# trouver ses variables requises (POSTGRES_*, DATABASE_URL, JWT_SIGNING_KEY)
# — via `.env` en local, via des valeurs factices exportées par la CI
# (.github/workflows/ci.yml), symétrique à `test_openapi.py`.
#
# Lancé via `uv run python src/export_openapi.py` (cwd = back/), même
# convention que main.py/worker.py — jamais importé comme module.


def main() -> None:
    schema = create_app().openapi()
    print(json.dumps(schema, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
