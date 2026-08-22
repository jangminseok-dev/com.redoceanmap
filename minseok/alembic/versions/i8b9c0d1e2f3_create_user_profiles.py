"""프로파일 — user_profiles 생성 (개인화 ⓪ 투자·창업 프로파일)

Revision ID: i8b9c0d1e2f3
Revises: h7a8b9c0d1e2
Create Date: 2026-08-22

자기신고 설문(목적·투자성향·예산 밴드·부채 부담·투자 기간) — 사용자당 1행.
정확한 금액·계좌·신용점수는 받지 않고 밴드(구간)만 저장한다(개인 금융 정보 부담 최소화).
북마크와 같은 "사용자 ↔ 분석 대상" 축이라 recommendation 스포크가 소유한다.
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "i8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "h7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(8), nullable=False),       # startup | invest | both
        sa.Column("risk_level", sa.Integer(), nullable=False),    # 1~5 (투자성향 5등급)
        sa.Column("budget_band", sa.String(16), nullable=False),  # under_30m ~ over_300m
        sa.Column("debt_burden", sa.String(12), nullable=False),  # none | manageable | heavy
        sa.Column("horizon", sa.String(8), nullable=False),       # short | mid | long
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint("user_id", name="uq_user_profiles_user_id"),
    )
    op.create_index("ix_user_profiles_user_id", "user_profiles", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_profiles_user_id", table_name="user_profiles")
    op.drop_table("user_profiles")
