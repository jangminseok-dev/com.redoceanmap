"""북마크 — bookmarks 생성 (③-M2 관심 종목·상권)

Revision ID: h7a8b9c0d1e2
Revises: h6f7a8b9c0d1
Create Date: 2026-08-21

사용자 ↔ 분석 대상(종목/상권) 연결. 추천 기록과 같은 성격이라 recommendation 스포크가
소유한다(ROADMAP 판정 — CRUD 2~3개짜리 새 스포크는 과설계). label은 저장 시점 표시명 동결.
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "h7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "h6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bookmarks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(8), nullable=False),  # stock | area
        sa.Column("target_key", sa.String(30), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id", "target_type", "target_key", name="uq_bookmarks_user_target",
        ),
    )
    op.create_index("ix_bookmarks_user_id", "bookmarks", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_bookmarks_user_id", table_name="bookmarks")
    op.drop_table("bookmarks")
