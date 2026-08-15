"""refresh_token : rotation avec détection de rejeu (C6)

Revision ID: 177dd65ff490
Revises: 322c2ef784b8
Create Date: 2026-08-15 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "177dd65ff490"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "322c2ef784b8"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "refresh_token",
        sa.Column("jti", sa.UUID(), nullable=False),
        sa.Column("family_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_refresh_token_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("jti", name=op.f("pk_refresh_token")),
    )
    op.create_index(
        op.f("ix_refresh_token_family_id"), "refresh_token", ["family_id"], unique=False
    )
    op.create_index(op.f("ix_refresh_token_user_id"), "refresh_token", ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_refresh_token_user_id"), table_name="refresh_token")
    op.drop_index(op.f("ix_refresh_token_family_id"), table_name="refresh_token")
    op.drop_table("refresh_token")
