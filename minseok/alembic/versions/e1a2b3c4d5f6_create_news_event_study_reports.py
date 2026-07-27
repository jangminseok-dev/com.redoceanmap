"""create news_event_study_reports

뉴스 이벤트 사후 수익률 연구 리포트(실행당 1행). `area_score_backtest_reports`와
같은 형태 — 코퍼스 전역 집계라 요청마다 계산하지 않고 배치가 써두면 어드민이 읽는다.

Revision ID: e1a2b3c4d5f6
Revises: d2e3f4a5b6c7
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e1a2b3c4d5f6"
down_revision: Union[str, Sequence[str], None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "news_event_study_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "ran_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("news_event_study_reports")
