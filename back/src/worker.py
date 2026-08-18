import uvicorn

from composition import create_worker_app

# Point d'entrée séparé du processus `worker` (F2, backlog.md) — pendant
# `main.py` (`api`), symétrique côté docker-compose.yml (service `worker`,
# `command: ["uv", "run", "python", "src/worker.py"]`). `app` reste
# exposable via `uvicorn worker:app` (mêmes outils que `main.py`, ex.
# tests) ; le bloc `__main__` ci-dessous couvre le lancement direct par ce
# `command` docker-compose, qui n'invoque pas la CLI `uvicorn`.
app = create_worker_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
