import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from composition import create_app


@pytest.fixture
def env_minimal(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mêmes valeurs que tests/composition/test_openapi.py — construire le
    # schéma OpenAPI ne fait aucune I/O, seule `Settings` doit trouver ses
    # champs requis pour s'instancier (voir export_openapi.py).
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
    )
    monkeypatch.setenv("JWT_SIGNING_KEY", "cle-de-test-suffisamment-longue-32c")


def test_export_openapi_produit_le_meme_schema_que_lapp(env_minimal: None) -> None:
    # H2 (backlog.md) : le script que la CI et scripts/generate-api-client.sh
    # invoquent doit imprimer *exactement* le schéma que `create_app()`
    # exposerait — sinon le client TS régénéré ne correspond plus à l'API
    # réellement montée.
    src_dir = Path(__file__).resolve().parents[2] / "src"
    resultat = subprocess.run(
        [sys.executable, str(src_dir / "export_openapi.py")],
        cwd=src_dir,
        capture_output=True,
        text=True,
        check=True,
        env=os.environ.copy(),
    )

    schema_script = json.loads(resultat.stdout)
    schema_app = create_app().openapi()
    assert schema_script == schema_app
