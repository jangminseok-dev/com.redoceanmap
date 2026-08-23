"""알림 고도화(③-M3 후속) — user_alert_settings·user_alert_deliveries 생성

- user_alert_settings: 회원별 이메일 알림 수신 설정(사용자당 1행 — 행이 없으면 기본 수신).
- user_alert_deliveries: 마지막으로 통지한 (사용자, 종목, 방향) 상태 — 같은 신호가
  지속되는 동안 매일 반복 발송되는 v1 한계의 해소(dedupe). 신호가 꺼지면 행이 사라져
  다음 재발생 때 새 알림이 나간다.
둘 다 recommendation 스포크 소유(사용자↔분석대상 축 — 북마크·프로파일과 같은 판정).

Revision ID: l1e2f3a4b5c6
Revises: k0d1e2f3a4b5
Create Date: 2026-08-23
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "l1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "k0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_alert_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("email_alerts", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint("user_id", name="uq_user_alert_settings_user_id"),
    )
    op.create_index("ix_user_alert_settings_user_id", "user_alert_settings", ["user_id"])

    op.create_table(
        "user_alert_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(30), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),  # UP | DOWN
        sa.Column(
            "sent_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint("user_id", "ticker", name="uq_user_alert_deliveries_user_ticker"),
    )


def downgrade() -> None:
    op.drop_table("user_alert_deliveries")
    op.drop_index("ix_user_alert_settings_user_id", table_name="user_alert_settings")
    op.drop_table("user_alert_settings")
