"""가중치 재적합 리포트 — forecast_refit_reports 생성

Revision ID: h6f7a8b9c0d1
Revises: h5e6f7a8b9c0
Create Date: 2026-08-21

주 1회 재적합 배치의 실행당 1행 리포트(리더보드·승격 판정 payload).
`news_event_study_reports`(e1a2b3c4d5f6)와 동형 — payload 스키마 정의처는
`stock/domain/services/weight_refit.py`.
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "h6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "h5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "forecast_refit_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ran_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("params", JSONB(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("forecast_refit_reports")
