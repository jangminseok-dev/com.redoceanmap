"""add commercial trades (국토부 상업업무용 매매 실거래)

상권 축의 비용 공백(진입 비용)을 메운다 — 분기 팩트는 매출·인구만 있고 부동산 가격이 없다.
원본에 좌표가 없어 자치구(sggCd = region 자치구 코드, 동일 체계) 단위로 집계한다.
임대(전월세)는 국토부 공개 API에 없다(2026-08-21 확인) — 매매 축만 적재.
적재는 scripts/collect_commercial_trades.py — (sgg_cd, 거래 연월) 단위 교체 멱등.

Revision ID: c7d8e9f0a1b2
Revises: b5c6d7e8f9a0
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, Sequence[str], None] = "b5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "commercial_trades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sgg_cd", sa.String(length=5), nullable=False),
        sa.Column("sgg_nm", sa.String(length=20), nullable=False),
        sa.Column("umd_nm", sa.String(length=20), nullable=False),
        sa.Column("jibun", sa.String(length=20), nullable=True),
        sa.Column("building_type", sa.String(length=8), nullable=False),
        sa.Column("building_use", sa.String(length=30), nullable=True),
        sa.Column("land_use", sa.String(length=30), nullable=True),
        sa.Column("floor", sa.Integer(), nullable=True),
        sa.Column("build_year", sa.Integer(), nullable=True),
        sa.Column("building_ar", sa.Float(), nullable=False),
        sa.Column("deal_amount", sa.Float(), nullable=False),
        sa.Column("deal_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_commercial_trades_sgg_deal", "commercial_trades",
                    ["sgg_cd", "deal_date"])


def downgrade() -> None:
    op.drop_index("ix_commercial_trades_sgg_deal", table_name="commercial_trades")
    op.drop_table("commercial_trades")
