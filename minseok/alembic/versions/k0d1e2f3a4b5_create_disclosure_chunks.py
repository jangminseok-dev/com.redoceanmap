"""청킹 실험(R3) — disclosure_chunks 생성

DART 사업보고서(한국 10사 × 최신 1건)를 전략별(a 고정 토큰 / b 섹션 / c 표 인지)로
청킹해 나란히 저장하는 실험 코퍼스. 적재는 scripts/collect_disclosures.py —
(rcept_no, strategy) 단위 교체 멱등. 벡터 인덱스 없음(수천 청크 — 브루트포스).

Revision ID: k0d1e2f3a4b5
Revises: j9c0d1e2f3a4
Create Date: 2026-08-23
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "k0d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = "j9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "disclosure_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("corp_code", sa.String(8), nullable=False),
        sa.Column("corp_name", sa.String(40), nullable=False),
        sa.Column("rcept_no", sa.String(14), nullable=False),
        sa.Column("strategy", sa.String(1), nullable=False),   # a | b | c
        sa.Column("section_path", sa.String(300), nullable=False, server_default=""),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),       # text | table
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint(
            "rcept_no", "strategy", "chunk_index",
            name="uq_disclosure_chunks_doc_strategy_index",
        ),
    )
    op.create_index("ix_disclosure_chunks_strategy", "disclosure_chunks", ["strategy"])


def downgrade() -> None:
    op.drop_index("ix_disclosure_chunks_strategy", table_name="disclosure_chunks")
    op.drop_table("disclosure_chunks")
