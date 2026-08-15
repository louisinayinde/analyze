import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
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


class RefreshTokenModel(Base):
    """Table `refresh_token` (C6) : état stateful minimal de la rotation.

    Le JWT refresh reste vérifiable sans cette table (signature + `exp`,
    voir `EmetteurJWT.decoder_refresh`) ; seule sa consommation
    (utilisé/révoqué) est stockée ici, car aucune signature ne peut le
    prouver. Modèle de persistance pur, sans règle métier — seul
    `DépôtRefreshTokenPostgres` connaît cette classe (agents.md §4).
    """

    __tablename__ = "refresh_token"

    # Le `jti` du JWT sert directement de clé primaire : c'est déjà un
    # identifiant unique généré à l'émission (`EmetteurJWT`), le dupliquer
    # sous un second id serait une même connaissance à deux endroits
    # (agents.md §1, DRY).
    jti: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    # Constant sur toute une chaîne de rotation : c'est cet identifiant, pas
    # le `jti` individuel, qui est révoqué en bloc sur détection de rejeu.
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Reflet de l'`exp` encodé dans le JWT au moment de l'émission : sert à
    # une purge/audit ultérieurs, jamais revérifié dans le use-case (le
    # décodage du JWT a déjà rejeté un jeton expiré avant que cette ligne ne
    # soit même consultée — agents.md §1, pas de double contrôle de la même
    # connaissance).
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Posé par la rotation nominale : ce refresh a été échangé contre une
    # nouvelle paire.
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Posé sur toute la famille dès qu'un rejeu est détecté sur l'un de ses
    # jetons (`RafraichirJetons`).
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
