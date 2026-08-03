"""게임 포지션에 레버리지·만료·마감사유·상품구분을 추가한다.

18단계(레버리지)와 19단계(선물)가 같은 컬럼을 쓴다 — 선물도 만기와 증거금을 가진
포지션이라 `game_positions`를 그대로 재사용한다(새 테이블 0개).

기존 행은 server_default로 `STOCK / 1배 / 만료 없음 / 마감사유 없음`이 되어 **도입 전과
정확히 같은 의미**를 유지한다. 1배는 청산도 만료도 되지 않는다.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'game_positions',
        sa.Column('instrument', sa.String(8), nullable=False, server_default='STOCK'),
    )
    op.add_column(
        'game_positions',
        sa.Column('leverage', sa.Integer(), nullable=False, server_default='1'),
    )
    # 만료는 레버리지·선물 포지션에만 있다. 1배 주식은 NULL이며 마감 판정 대상이 아니다.
    op.add_column('game_positions', sa.Column('expires_tick', sa.Integer(), nullable=True))
    # user | liquidated | expired | settled — 유저 청산이면 NULL이 아니라 'user'를 남긴다
    op.add_column('game_positions', sa.Column('close_reason', sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column('game_positions', 'close_reason')
    op.drop_column('game_positions', 'expires_tick')
    op.drop_column('game_positions', 'leverage')
    op.drop_column('game_positions', 'instrument')
