from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration lue depuis l'environnement (agents.md §7 : rien en dur).

    Aucune valeur par défaut sur les champs sensibles : si une variable
    manque, le démarrage échoue explicitement plutôt que de tourner avec
    une valeur fantôme.
    """

    model_config = SettingsConfigDict(
        # "../.env" pour un lancement local hors docker (cwd = back/),
        # ".env" si l'app est lancée depuis la racine du repo. En conteneur,
        # les variables sont déjà injectées via env_file du docker-compose ;
        # ces fichiers sont simplement absents et donc ignorés.
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_user: str
    postgres_password: str
    postgres_db: str

    database_url: str

    # Pool de connexions borné (agents.md §2, §3 ; projets.md §Base de
    # données) : Cloud Run scale-to-zero peut redémarrer plusieurs
    # instances d'un coup, chacune ouvrant son propre pool. Des valeurs
    # basses par défaut évitent qu'une pointe de trafic ne sature les
    # connexions max de Postgres/Cloud SQL. Ajustables par service via
    # l'environnement si un besoin réel de charge le justifie.
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_timeout_seconds: int = 30
    db_pool_recycle_seconds: int = 1800

    jwt_signing_key: str

    # « Quelques minutes » (projets.md §Sécurité, backlog C4) : une fuite de
    # l'access token n'est exploitable que sur cette fenêtre. Le refresh,
    # lui, vit en cookie httpOnly (front, J3) — sa fenêtre plus large est
    # compensée par la rotation à chaque usage prévue en C6.
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30

    # Vide tant que l'intégration LLM (EPIC E) n'est pas branchée.
    llm_api_key: str = ""

    cors_origins: str = ""

    log_level: str = "INFO"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    # mypy ignore les valeurs par défaut de pydantic-settings.BaseSettings :
    # il croit ces champs requis en argument alors qu'ils sont peuplés
    # depuis l'environnement à l'exécution.
    return Settings()  # type: ignore[call-arg]
