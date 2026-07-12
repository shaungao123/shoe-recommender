"""enable pgvector, create embeddings table

Revision ID: e582eb654d21
Revises: 3a623e47157a
Create Date: 2026-07-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'e582eb654d21'
down_revision: Union[str, Sequence[str], None] = '3a623e47157a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 1536  # text-embedding-3-small


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        'embeddings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('shoe_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('source', sa.String(length=64), nullable=True),
        sa.Column('model_id', sa.String(length=128), nullable=False),
        sa.Column('vector', Vector(EMBEDDING_DIM), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['shoe_id'], ['shoes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_embeddings_shoe_id'), 'embeddings', ['shoe_id'], unique=False)
    # HNSW over cosine distance — the retriever must query with `<=>`.
    op.execute(
        "CREATE INDEX ix_embeddings_vector_hnsw ON embeddings "
        "USING hnsw (vector vector_cosine_ops)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_embeddings_vector_hnsw', table_name='embeddings')
    op.drop_index(op.f('ix_embeddings_shoe_id'), table_name='embeddings')
    op.drop_table('embeddings')
    # The vector extension is left installed; other objects may depend on it.
