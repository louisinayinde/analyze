import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

cors_origins = [
    origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["GET"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
