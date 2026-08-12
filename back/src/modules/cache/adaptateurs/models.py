import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class SourceType(enum.StrEnum):
    """Catégorie du texte collé par l'user (projets.md, §1 : profil GitHub,
    historique d'écoute, bio, ou tout autre texte libre). Fait partie du
    calcul de `input_hash` (D2 : hash du texte normalisé + `source_type`),
    donc deux mêmes textes de sources différentes ne partagent pas le cache.

    Valeurs déduites du pitch (projets.md n'énumère pas de liste figée) ;
    `AUTRE` couvre toute source non prévue explicitement. Un ajout de
    valeur future se fait par migration additive (Postgres `ALTER TYPE
    ... ADD VALUE`), sans casser les lignes existantes.
    """

    GITHUB = "github"
    SPOTIFY = "spotify"
    BIO = "bio"
    AUTRE = "autre"


class StatutCache(enum.StrEnum):
    """Statut du job de génération, piloté par l'algorithme de concurrence
    de projets.md (§Concurrence sur le cache) : `pending` posé par un
    `INSERT ... ON CONFLICT DO NOTHING`, puis transitionné vers `done` ou
    `failed` par le worker (D3, EPIC F).
    """

    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


def _enum_par_valeur(enum_cls: type[enum.StrEnum], name: str) -> Enum:
    """Type Postgres qui stocke `.value` (ex. "pending"), pas le nom du
    membre Python (ex. "PENDING") — comportement par défaut de SQLAlchemy,
    qui romprait `server_default=StatutCache.PENDING.value` : le type
    Postgres ne connaîtrait alors que le label "PENDING".
    """
    return Enum(enum_cls, name=name, values_callable=lambda cls: [e.value for e in cls])


class CacheResultatModel(Base):
    """Table `cache_resultat` (projets.md, section Base de données).

    Cache exact partagé entre tous les users — le cœur de la promesse de
    coût du projet (projets.md §1). Modèle de persistance pur, connu
    uniquement de l'adaptateur `CachePort` Postgres (D2) ; aucune règle
    métier ici (agents.md §4).
    """

    __tablename__ = "cache_resultat"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # sha256 hex digest = 64 caractères (D2 : hash du texte normalisé +
    # source_type). Unique + indexé : c'est la clé du cache exact.
    input_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source_type: Mapped[SourceType] = mapped_column(_enum_par_valeur(SourceType, "source_type"))
    status: Mapped[StatutCache] = mapped_column(
        _enum_par_valeur(StatutCache, "statut_cache"), server_default=StatutCache.PENDING.value
    )
    # Nullable : absents tant que `status` n'est pas `done`.
    output_text: Mapped[str | None] = mapped_column(Text)
    output_image_url: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Métrique directe de l'économie de cache (projets.md §Observabilité :
    # "le chiffre qui vend le projet"). Incrémenté à chaque cache-hit.
    hit_count: Mapped[int] = mapped_column(Integer, server_default="0")
