"""활성 판정 조합 DB화 — forecast_signal_configs 생성 + 현행 조합 시드

Revision ID: h5e6f7a8b9c0
Revises: g4d5e6f7a8b9
Create Date: 2026-08-21

판정 조합(`AnalysisConfig.forecast_signal()`)이 코드 상수로 박혀 있어 재적합 배치가
승격을 반영할 수 없었다. 활성 조합을 행으로 옮기고, 주 1회 재적합이 게이트 통과 시
새 행을 INSERT + 활성 전환한다(코드 폴백은 행 부재 시에만).

- 부분 유니크 인덱스: 활성 조합은 항상 정확히 1개(WHERE is_active) — 동시 활성을 DB가 막는다.
- 필드 전개(JSONB 아님): 조합 파라미터는 스키마가 고정된 손잡이 값이다. JSONB payload는
  "실행당 1행 리포트" 전용 선례(news_event_study_reports)를 따른다.
- 시드: 현행 `forecast_signal()` 값을 `forecast_signal` 키로 — 기존 스냅샷의
  signal_config 문자열과 이어져 이력이 끊기지 않는다.
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "h5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "g4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "forecast_signal_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("config_key", sa.String(24), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("up_threshold", sa.Float(), nullable=False),
        sa.Column("down_threshold", sa.Float(), nullable=False),
        sa.Column("w_sentiment", sa.Float(), nullable=False),
        sa.Column("w_rsi", sa.Float(), nullable=False),
        sa.Column("w_trend", sa.Float(), nullable=False),
        sa.Column("w_bb", sa.Float(), nullable=False),
        sa.Column("w_obv", sa.Float(), nullable=False),
        sa.Column("w_momentum", sa.Float(), nullable=False),
        sa.Column("atr_veto", sa.Float(), nullable=True),
        sa.Column("volume_confirm", sa.Float(), nullable=True),
        sa.Column("source", sa.String(8), nullable=False),  # seed | refit
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_forecast_signal_configs_active",
        "forecast_signal_configs",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    # 현행 코드 상수(AnalysisConfig.forecast_signal())를 활성 시드로 — 동작 불변 전환
    op.execute(
        """
        INSERT INTO forecast_signal_configs
            (config_key, is_active, up_threshold, down_threshold,
             w_sentiment, w_rsi, w_trend, w_bb, w_obv, w_momentum,
             atr_veto, volume_confirm, source, activated_at)
        VALUES
            ('forecast_signal', true, 0.35, -1.01,
             0.0, 0.4, 0.0, 0.4, 0.0, 0.2,
             NULL, NULL, 'seed', now())
        """
    )


def downgrade() -> None:
    op.drop_index("uq_forecast_signal_configs_active", table_name="forecast_signal_configs")
    op.drop_table("forecast_signal_configs")
