"""user_alert_settings에 telegram_chat_id 추가(I-7) — 텔레그램 알림 채널.

Revision ID: m2f3a4b5c6d7
Revises: l1e2f3a4b5c6
"""
from alembic import op
import sqlalchemy as sa

revision = "m2f3a4b5c6d7"
down_revision = "l1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_alert_settings",
        sa.Column("telegram_chat_id", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_alert_settings", "telegram_chat_id")
