"""위험 신호 검증 리포트 — risk_signal_reports 생성

Revision ID: r7e8f9a0b1c2
Revises: q6d7e8f9a0b1
Create Date: 2026-09-17

신호 보드 재설계(방향 → 위험). 주 1회 백테스트의 실행당 1행 — 상태별 학습/검증 발생률·기준률·검증 여부.
`forecast_refit_reports`(h6f7a8b9c0d1)와 동형 — payload 스키마 정의처는
`stock/domain/services/risk_signal_backtester.py`.
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "r7e8f9a0b1c2"
down_revision: Union[str, Sequence[str], None] = "q6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "risk_signal_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ran_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("params", JSONB(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("risk_signal_reports")
