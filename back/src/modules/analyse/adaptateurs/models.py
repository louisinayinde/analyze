import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class HistoriqueModel(Base):
    """Table `historique` (projets.md, section Base de données).

    « Ce que l'auth débloque : historique personnel » — rattachée au module
    `analyse` (pas un module dédié) car chaque ligne naît du use-case
    `GenererAnalyse` (D3) : à chaque analyse d'un user authentifié, une
    ligne `historique` est créée en plus du (ou en plus de la référence au)
    `cache_resultat` partagé. Modèle de persistance pur (agents.md §4) :
    aucune règle métier, connu uniquement de l'adaptateur qui implémentera
    l'écriture d'historique dans D3/H3.

    Les FK vers `user` (module `auth`) et `cache_resultat` (module `cache`)
    sont une relation au niveau du schéma SQL, pas un import Python : elles
    n'enfreignent pas la règle « un module ne parle à un autre que par son
    index » (agents.md §4), qui s'applique au code, pas à l'intégrité
    référentielle portée par la base.
    """

    __tablename__ = "historique"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # ON DELETE CASCADE : `DELETE /compte` (H3) doit effacer l'historique
    # personnel de l'user avec son compte — l'`input_text` collé est une
    # donnée personnelle (agents.md §3 : confidentialité visible dans le
    # schéma), elle ne doit pas survivre à la suppression du compte.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), index=True
    )
    # Pas d'ON DELETE : `cache_resultat` est une donnée partagée entre tous
    # les users, sans mécanisme de purge/rétention défini à ce stade (hors
    # scope v1, projets.md). Comportement par défaut (RESTRICT) : à revoir
    # via ADR le jour où une politique de rétention du cache est décidée.
    resultat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cache_resultat.id"), index=True
    )
    # Copie du texte original collé par cet user (projets.md) : distincte du
    # texte normalisé utilisé pour `input_hash` côté `cache_resultat` — sert
    # à réafficher l'historique personnel tel que l'user l'a saisi.
    input_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
