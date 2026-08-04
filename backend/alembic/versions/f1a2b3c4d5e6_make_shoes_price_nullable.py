"""make shoes.price nullable

Revision ID: f1a2b3c4d5e6
Revises: e582eb654d21
Create Date: 2026-07-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e582eb654d21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('shoes', 'price', existing_type=sa.Numeric(10, 2), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('shoes', 'price', existing_type=sa.Numeric(10, 2), nullable=False)
