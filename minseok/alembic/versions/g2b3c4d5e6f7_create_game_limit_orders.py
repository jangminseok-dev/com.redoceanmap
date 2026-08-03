"""지정가 주문 테이블 (12단계)

Revision ID: g2b3c4d5e6f7
Revises: g1a2b3c4d5e6
Create Date: 2026-08-03

게임은 주가를 저장하지 않지만(game-harness §4-2) **유저의 의도**는 난수에서 유도할 수 없어
저장한다 — 주가 개입 테이블과 같은 성격이다.

체결은 cron이 아니라 조회 시점에 판정한다(game-strategy §7-12, 8단계 결산과 같은 지연 실행).
그래서 스캔 범위를 묶는 `placed_tick`·`expires_tick`이 성능의 핵심 컬럼이다.

익절·손절 쌍(OCO)은 별도 그룹 컬럼 없이 **같은 `position_id`** 로 묶는다 —
한쪽이 체결되면 그 포지션의 나머지 대기 주문을 취소한다.
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "g2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "g1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "game_limit_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("epoch_id", sa.Integer(), nullable=False),
        # ENTRY(진입 예약) | EXIT(청산 예약 — 익절·손절)
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),  # LONG | SHORT
        # EXIT일 때만 채워진다. 대상 포지션이 닫히면 남은 대기 주문도 함께 정리한다.
        sa.Column("position_id", sa.Integer(), nullable=True),
        sa.Column("trigger", sa.String(length=2), nullable=False),  # le(이하) | ge(이상)
        sa.Column("limit_price_krw", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("leverage", sa.Integer(), server_default="1", nullable=False),
        sa.Column("placed_tick", sa.Integer(), nullable=False),
        # 스캔 범위 상한 — 이 값이 없으면 장기 미접속 유저의 판정 비용이 폭발한다.
        sa.Column("expires_tick", sa.Integer(), nullable=False),
        # pending | filled | cancelled | expired
        sa.Column("status", sa.String(length=12), server_default="pending", nullable=False),
        sa.Column("filled_tick", sa.Integer(), nullable=True),
        sa.Column("filled_price_krw", sa.BigInteger(), nullable=True),
        # 진입 예약이 묶어둔 현금 — 체결·취소·만료 때 그대로 정산한다.
        sa.Column("reserved_cash_krw", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["position_id"], ["game_positions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # 판정은 항상 "이 유저의 대기 주문 전부"로 시작한다.
    op.create_index(
        "ix_game_limit_orders_user_status", "game_limit_orders", ["user_id", "status"]
    )
    # OCO 취소·포지션 청산 시 남은 예약 정리 경로.
    op.create_index("ix_game_limit_orders_position", "game_limit_orders", ["position_id"])


def downgrade() -> None:
    op.drop_index("ix_game_limit_orders_position", table_name="game_limit_orders")
    op.drop_index("ix_game_limit_orders_user_status", table_name="game_limit_orders")
    op.drop_table("game_limit_orders")
