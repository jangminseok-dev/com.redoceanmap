"""알림 묶음([6] 가격 도달 + B9 뉴스) — user_price_alerts·news_alert_cursor 생성

- user_price_alerts: 사용자가 직접 건 가격 조건(손절·익절선). 도달 시 1회 통지 후
  active=false(one-shot). `user_alert_deliveries`를 재사용하지 않는 이유: 그 테이블은
  북마크 스캔이 매 실행 **전체 교체**(delete-all)하므로 다른 스캔이 섞이면 서로의
  dedupe 상태를 지운다. recommendation 스포크 소유(사용자↔분석대상 축 — 북마크 선례).
- news_alert_cursor: B9 뉴스 알림의 워터마크(마지막으로 처리한 news_labels.id) 단일 행.
  라벨 적재분 중 커서 이후만 알림 후보로 뽑아 중복 발송을 구조적으로 막는다.
  stock 스포크 소유(news_labels와 같은 축).

Revision ID: n3a4b5c6d7e8
Revises: m2f3a4b5c6d7
Create Date: 2026-09-01
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "n3a4b5c6d7e8"
down_revision: Union[str, Sequence[str], None] = "m2f3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_price_alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(30), nullable=False),
        sa.Column("target_price", sa.Float(), nullable=False),
        sa.Column("direction", sa.String(5), nullable=False),  # above | below
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index("ix_user_price_alerts_user_id", "user_price_alerts", ["user_id"])
    # 스캔은 active 행만 훑는다 — 트리거된 이력 행이 쌓여도 스캔 비용이 안 늘게 부분 인덱스
    op.create_index(
        "ix_user_price_alerts_active", "user_price_alerts", ["active"],
        postgresql_where=sa.text("active"),
    )

    op.create_table(
        "news_alert_cursor",
        sa.Column("id", sa.Integer(), primary_key=True),  # 단일 행(id=1)
        sa.Column("last_label_id", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("news_alert_cursor")
    op.drop_index("ix_user_price_alerts_active", table_name="user_price_alerts")
    op.drop_index("ix_user_price_alerts_user_id", table_name="user_price_alerts")
    op.drop_table("user_price_alerts")
