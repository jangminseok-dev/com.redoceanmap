"""add rent_benchmarks + interest_rates (창업 재무 엔진 — 비용·손익 축)

R-ONE 상가 임대료·공실률(서울 64 CLS × 분기)과 ECOS 금리(월)를 market 전용 DB에 둔다.
임대료는 상권 59곳뿐이라 권역 평균 폴백이 기본이다(FINANCE_ENGINE_2026-09-16).

Revision ID: f5a6b7c8d9e0
Revises: e9a1b2c3d4e5
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, Sequence[str], None] = "e9a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rent_benchmarks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("building_type", sa.String(16), nullable=False),
        sa.Column("year_quarter", sa.Integer(), nullable=False),
        sa.Column("cls_id", sa.String(16), nullable=False),
        sa.Column("cls_fullnm", sa.String(80), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("region_name", sa.String(40), nullable=False),
        sa.Column("rent_per_sqm_krw", sa.Integer(), nullable=False),
        sa.Column("vacancy_rate", sa.Float(), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("building_type", "year_quarter", "cls_id", name="uq_rent_benchmarks_type_quarter_cls"),
    )
    op.create_index("ix_rent_benchmarks_year_quarter", "rent_benchmarks", ["year_quarter"])
    op.create_index("ix_rent_benchmarks_region_name", "rent_benchmarks", ["region_name"])
    op.create_table(
        "interest_rates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stat_code", sa.String(16), nullable=False),
        sa.Column("item_name", sa.String(60), nullable=False),
        sa.Column("year_month", sa.Integer(), nullable=False),
        sa.Column("rate", sa.Float(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("stat_code", "item_name", "year_month", name="uq_interest_rates_stat_item_month"),
    )
    op.create_index("ix_interest_rates_year_month", "interest_rates", ["year_month"])


def downgrade() -> None:
    op.drop_index("ix_interest_rates_year_month", table_name="interest_rates")
    op.drop_table("interest_rates")
    op.drop_index("ix_rent_benchmarks_region_name", table_name="rent_benchmarks")
    op.drop_index("ix_rent_benchmarks_year_quarter", table_name="rent_benchmarks")
    op.drop_table("rent_benchmarks")
