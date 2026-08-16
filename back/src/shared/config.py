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

    # Vide par défaut : le point de composition (composition/app.py) reste
    # alors sur `GenerateurIAFactice` plutôt que d'exiger une clé Anthropic
    # payante pour lancer l'API en dev local (agents.md §2, budget).
    # Renseignée -> `AdaptateurClaude` (E1 texte, E2 image) est câblé à la
    # place, sans changement de code.
    llm_api_key: str = ""

    # Modèle Claude utilisé par AdaptateurClaude (E1). Haiku par défaut :
    # un roast de quelques phrases ne justifie pas un modèle frontier
    # (agents.md §2, budget). Changer de modèle = changer cette valeur,
    # aucune ligne de code (agents.md §4 : décision réversible).
    llm_model: str = "claude-haiku-4-5"

    cors_origins: str = ""

    log_level: str = "INFO"

    # `StockageImagePort` (E5, backlog.md) : vide par défaut -> adaptateur
    # filesystem local (dev, écrit sur le volume Docker `images_data`,
    # voir docker-compose.yml). Renseigné -> `StockageImageGCS` est câblé à
    # la place (composition/app.py), sans changement de code — même bascule
    # que `llm_api_key` ci-dessus, activée seulement une fois le bucket
    # provisionné par L4 (backlog.md).
    gcs_bucket_images: str = ""

    # Dossier d'écriture de l'adaptateur filesystem, relatif au `WORKDIR`
    # du conteneur `api` (`/app`, voir Dockerfile.dev). Isolé du bind mount
    # `./back:/app` par un volume Docker dédié (docker-compose.yml) : sans
    # ça, chaque image générée en dev finirait committée dans le dépôt.
    local_storage_dir: str = "data/images"

    # URL depuis laquelle le navigateur atteint l'API (pas le nom de
    # service Docker `api`, résolvable seulement entre conteneurs) : sert à
    # construire l'URL publique d'une image stockée en local
    # (`{api_public_url}/images/{cle}.png`). Doit rester cohérent avec
    # `NEXT_PUBLIC_API_URL` (front) en dev.
    api_public_url: str = "http://localhost:8000"

    # `FileJobsPort` (F1, backlog.md) : vide par défaut -> adaptateur
    # `FileJobsEnProcessusImmediat` (dev, exécute le job en synchrone dans
    # le même processus, pas besoin de Cloud Tasks en local). Renseignée ->
    # `FileJobsCloudTasks` est câblé à la place (composition/app.py),
    # activé seulement une fois L7 fait (provisionnement Terraform de la
    # queue) — même bascule que `gcs_bucket_images`/`llm_api_key` ci-dessus
    # (agents.md §2).
    cloud_tasks_queue: str = ""

    # Requis seulement si `cloud_tasks_queue` est renseignée : projet et
    # région GCP de la queue, URL interne du service `worker` (F3,
    # backlog.md) qui recevra les tâches, et service account utilisé pour
    # signer le jeton OIDC que F3 vérifiera à réception — l'endpoint
    # interne du worker ne doit pas être appelable par n'importe qui
    # (agents.md §7).
    gcp_project_id: str = ""
    gcp_region: str = ""
    worker_internal_url: str = ""
    worker_service_account_email: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    # mypy ignore les valeurs par défaut de pydantic-settings.BaseSettings :
    # il croit ces champs requis en argument alors qu'ils sont peuplés
    # depuis l'environnement à l'exécution.
    return Settings()  # type: ignore[call-arg]
