"""add canonical_id to shoes

Revision ID: 3a623e47157a
Revises: b0f17af1f14c
Create Date: 2026-07-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a623e47157a'
down_revision: Union[str, Sequence[str], None] = 'b0f17af1f14c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('shoes', sa.Column('canonical_id', sa.String(length=256), nullable=True))
    op.create_index(op.f('ix_shoes_canonical_id'), 'shoes', ['canonical_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_shoes_canonical_id'), table_name='shoes')
    op.drop_column('shoes', 'canonical_id')
