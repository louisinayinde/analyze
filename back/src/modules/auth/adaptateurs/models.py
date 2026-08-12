import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class UtilisateurModel(Base):
    """Table `user` (projets.md, section Base de données).

    Modèle de persistance pur : aucune règle métier ici (agents.md §4).
    Seul l'adaptateur `DépôtUtilisateurPostgres` (C2) connaît cette classe ;
    le domaine Auth manipule une entité `Utilisateur` distincte, définie
    côté `domaine/` (C1), sans dépendance à SQLAlchemy.
    """

    __tablename__ = "user"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # 320 = longueur max théorique d'une adresse email (RFC 5321 : 64 partie
    # locale + 1 "@" + 255 domaine).
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Nullable : absente tant que l'utilisateur ne s'est jamais connecté
    # (juste après l'inscription, C3).
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
