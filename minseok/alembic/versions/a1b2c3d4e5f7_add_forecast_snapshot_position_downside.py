"""예측 스냅샷에 판정 조합·원시 지표·하방/회복 통계 추가.

배경(2026-07-30): 스냅샷 814건이 전부 NEUTRAL이고 채점 123건이 전부 hit NULL이었다.
감성 중립 경로에 감성 가중치 0.5짜리 default() 조합을 써서 도달 가능한 |score| 상한이
0.2 < 임계 0.3이었던 것 — 조합을 forecast_signal()로 교체하면서 세 종류를 함께 남긴다.

1) signal_config — 어느 조합으로 낸 판정인가. **NULL = 교체 이전 default() 조합**이라
   이력을 섞어 읽지 않게 한다(기존 행은 백필하지 않는다 — 그 판정은 실제로 구 조합이다).
2) 원시 지표(rsi·bb_percent_b·momentum_12_1·atr_pct) + 위치(고점 대비 낙폭·지지선 여력) —
   signals JSONB에는 정규화 신호만 있어 RSI 실값을 복원할 수 없다. 가중치 재적합의 피처.
3) 하방·회복 기대치(trough_*·recovery_*)와 채점 시 실측(realized_trough_pct) —
   마감가만으로는 "얼마나 빠졌다 돌아왔는지"를 사후에 물을 수 없다. 오답 분석의 재료.

전부 nullable — 기존 814행은 그대로 두고 신규 캡처분만 채워진다.

Revision ID: a1b2c3d4e5f7
Revises: d7e8f9a0b1c2
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, Sequence[str], None] = 'd7e8f9a0b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FLOAT_COLUMNS = (
    # 캡처 시점 원시 지표 — 판정 재현·재적합용
    'rsi',
    'bb_percent_b',
    'momentum_12_1',
    'atr_pct',
    # 캡처 시점 위치
    'drawdown_from_high_pct',
    'above_support_pct',
    # 같은 신호의 과거 하방·회복 기대치
    'trough_median_pct',
    'trough_q25_pct',
    'recovery_rate',
    'recovery_days_median',
    # 채점 시 실측 하방
    'realized_trough_pct',
)


def upgrade() -> None:
    op.add_column(
        'forecast_snapshots',
        sa.Column('signal_config', sa.String(length=24), nullable=True),
    )
    for name in _FLOAT_COLUMNS:
        op.add_column('forecast_snapshots', sa.Column(name, sa.Float(), nullable=True))


def downgrade() -> None:
    for name in reversed(_FLOAT_COLUMNS):
        op.drop_column('forecast_snapshots', name)
    op.drop_column('forecast_snapshots', 'signal_config')
