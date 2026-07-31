"""게임 가게·운영결정 2종.

일일 매출은 저장하지 않는다 — 창업 시각과 결정만 있으면 어느 날이든 재계산된다
(game-harness §1-A). 저장하는 것은 유저의 행위(창업·결정)와 외부 사실의 스냅샷뿐이다.

`profile_snapshot`은 market 실데이터의 스냅샷이다. 기준 분기가 에포크에 박혀 있어 시즌
내내 값이 같으므로, 저장하는 이유는 일일 시뮬이 market DB를 왕복하지 않게 하려는 것이다.

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'game_stores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('trdar_code', sa.Integer(), nullable=False),
        sa.Column('service_code', sa.String(length=16), nullable=False),
        sa.Column('opened_game_day', sa.Integer(), nullable=False),
        sa.Column('closed_game_day', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('store_scale', sa.Float(), nullable=False),
        sa.Column('deposit_krw', sa.BigInteger(), nullable=False),
        sa.Column('interior_krw', sa.BigInteger(), nullable=False),
        sa.Column('profile_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('settled_through_day', sa.Integer(), nullable=False),
        sa.Column('epoch_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_game_stores_user_id', 'game_stores', ['user_id'])
    op.create_index('ix_game_stores_trdar_code', 'game_stores', ['trdar_code'])
    op.create_index('ix_game_stores_epoch_id', 'game_stores', ['epoch_id'])
    op.create_index('ix_game_stores_user_status', 'game_stores', ['user_id', 'status'])

    op.create_table(
        'game_store_decisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('store_id', sa.Integer(), nullable=False),
        sa.Column('effective_from_day', sa.Integer(), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('epoch_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['game_stores.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_game_store_decisions_store_id', 'game_store_decisions', ['store_id'])
    op.create_index('ix_game_store_decisions_epoch_id', 'game_store_decisions', ['epoch_id'])
    op.create_index(
        'ix_game_store_decisions_store_day',
        'game_store_decisions',
        ['store_id', 'effective_from_day'],
    )


def downgrade() -> None:
    op.drop_table('game_store_decisions')
    op.drop_table('game_stores')
