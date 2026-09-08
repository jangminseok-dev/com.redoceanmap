"""add franchise industry costs (공정위 가맹정보 업종별 창업비용)

상권 축의 예산 질문("1억이면 어디/어떤 업종")에 답할 첫 비용 팩트. 정보공개서 평균(가맹금·교육비·
보증금·기타 합계, 원)이라 점포 임대료·인테리어는 없다 — 소비자(chat)가 한계를 함께 말한다.
적재는 scripts/collect_franchise_costs.py → 허브 /automation/franchise-costs — (year, sector, industry_name) 교체 멱등.
2026-09-08 페르소나 QA(P01·P02·P08)에서 예산 질문 무답이 가장 큰 마찰이었다.

Revision ID: d8f0a1b2c3d4
Revises: d8e9f0a1b2c3
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "d8f0a1b2c3d4"
down_revision: Union[str, Sequence[str], None] = "d8e9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "franchise_industry_costs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("sector", sa.String(8), nullable=False),
        sa.Column("industry_name", sa.String(60), nullable=False),
        sa.Column("franchise_fee", sa.BigInteger(), nullable=False),
        sa.Column("education_fee", sa.BigInteger(), nullable=False),
        sa.Column("deposit", sa.BigInteger(), nullable=False),
        sa.Column("other_fee", sa.BigInteger(), nullable=False),
        sa.Column("total_amount", sa.BigInteger(), nullable=False),
        sa.Column("brand_count", sa.Integer(), nullable=True),
        sa.Column("raw", JSONB(), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("year", "sector", "industry_name", name="uq_franchise_industry_costs_year_sector_industry"),
    )
    op.create_index("ix_franchise_industry_costs_year", "franchise_industry_costs", ["year"])


def downgrade() -> None:
    op.drop_index("ix_franchise_industry_costs_year", table_name="franchise_industry_costs")
    op.drop_table("franchise_industry_costs")
