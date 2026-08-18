"""limite_debit : table du token bucket (G1)

Revision ID: 5deb14980b93
Revises: 177dd65ff490
Create Date: 2026-08-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5deb14980b93"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "177dd65ff490"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "limite_debit",
        sa.Column("cle", sa.String(), nullable=False),
        sa.Column("jetons", sa.Float(), nullable=False),
        sa.Column("maj_a", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("cle", name=op.f("pk_limite_debit")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("limite_debit")
