"""add anonymous feedback and product events

Revision ID: c9d4e2a7b1f0
Revises: f1a2b3c4d5e6
Create Date: 2026-11-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d4e2a7b1f0"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("shoe_id", sa.Integer(), sa.ForeignKey("shoes.id"), nullable=False),
        sa.Column("vote", sa.String(length=8), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("request_context", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_feedback_session_id", "feedback", ["session_id"])
    op.create_index("ix_feedback_shoe_id", "feedback", ["shoe_id"])
    op.create_table(
        "product_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("event_name", sa.String(length=64), nullable=False),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_product_events_session_id", "product_events", ["session_id"])
    op.create_index("ix_product_events_event_name", "product_events", ["event_name"])


def downgrade() -> None:
    op.drop_index("ix_product_events_event_name", table_name="product_events")
    op.drop_index("ix_product_events_session_id", table_name="product_events")
    op.drop_table("product_events")
    op.drop_index("ix_feedback_shoe_id", table_name="feedback")
    op.drop_index("ix_feedback_session_id", table_name="feedback")
    op.drop_table("feedback")
