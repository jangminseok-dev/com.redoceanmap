"""add key_money_benchmarks + rent_benchmarks 수익률 3열 (R-ONE 권리금·상가 수익률)

권리금: R-ONE A_2024_00445 시도별/업종별 상가권리금(연간, 2022~) — 재무 엔진의 "권리금 0 가정"을 서울 업종군 실측으로 교체.
수익률: 임대동향 수익률(분기, 2024Q3~) — 임대료 표와 (분기, CLS_ID)가 512행 전부 일치해 같은 테이블에 열로 둔다.

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "a6b7c8d9e0f1"
down_revision: Union[str, Sequence[str], None] = "f5a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("rent_benchmarks", sa.Column("income_return", sa.Float(), nullable=True))
    op.add_column("rent_benchmarks", sa.Column("capital_return", sa.Float(), nullable=True))
    op.add_column("rent_benchmarks", sa.Column("investment_return", sa.Float(), nullable=True))
    op.create_table(
        "key_money_benchmarks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("region_name", sa.String(20), nullable=False),
        sa.Column("industry_group", sa.String(60), nullable=False),
        sa.Column("key_money_ratio", sa.Float(), nullable=True),
        sa.Column("avg_krw", sa.BigInteger(), nullable=True),
        sa.Column("median_krw", sa.BigInteger(), nullable=True),
        sa.Column("per_sqm_avg_krw", sa.Integer(), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("year", "region_name", "industry_group", name="uq_key_money_year_region_group"),
    )


def downgrade() -> None:
    op.drop_table("key_money_benchmarks")
    op.drop_column("rent_benchmarks", "investment_return")
    op.drop_column("rent_benchmarks", "capital_return")
    op.drop_column("rent_benchmarks", "income_return")
