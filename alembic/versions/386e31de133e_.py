"""empty message

Revision ID: 386e31de133e
Revises: d78ff9ac0bc5
Create Date: 2026-08-15 15:02:47.573412

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "386e31de133e"
down_revision: str | Sequence[str] | None = "d78ff9ac0bc5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
