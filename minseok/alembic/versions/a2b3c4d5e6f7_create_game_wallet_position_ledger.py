"""게임 지갑·포지션·원장 3종.

모의투자와 상권 창업이 지갑 하나를 공유한다. 주가·이벤트는 시각의 함수라 저장하지 않지만
(game-harness §4-2) 지갑·포지션·원장은 유저 행위의 결과라 영속한다.

원장 불변식: SUM(game_ledger.amount_krw WHERE user_id) == game_wallets.cash_krw

Revision ID: a2b3c4d5e6f7
Revises: a1b2c3d4e5f7
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'game_wallets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('cash_krw', sa.BigInteger(), nullable=False),
        sa.Column('epoch_id', sa.Integer(), nullable=False),
        sa.Column('rule_version', sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    # 시즌마다 새 지갑이 생기지만 한 시즌에 유저당 하나뿐이다
    op.create_index('ix_game_wallets_user_id', 'game_wallets', ['user_id'], unique=True)
    op.create_index('ix_game_wallets_epoch_id', 'game_wallets', ['epoch_id'])

    op.create_table(
        'game_positions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=16), nullable=False),
        sa.Column('side', sa.String(length=8), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('entry_tick', sa.Integer(), nullable=False),
        sa.Column('entry_price_krw', sa.BigInteger(), nullable=False),
        sa.Column('entry_fee_krw', sa.BigInteger(), nullable=False),
        sa.Column('closed_tick', sa.Integer(), nullable=True),
        sa.Column('exit_price_krw', sa.BigInteger(), nullable=True),
        sa.Column('exit_fee_krw', sa.BigInteger(), nullable=True),
        sa.Column('carry_krw', sa.BigInteger(), nullable=True),
        sa.Column('realized_pnl_krw', sa.BigInteger(), nullable=True),
        sa.Column('epoch_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_game_positions_user_id', 'game_positions', ['user_id'])
    op.create_index('ix_game_positions_symbol', 'game_positions', ['symbol'])
    op.create_index('ix_game_positions_epoch_id', 'game_positions', ['epoch_id'])
    # 열린 포지션 조회가 가장 잦다 — 지갑 화면이 매 폴링마다 부른다
    op.create_index(
        'ix_game_positions_user_open', 'game_positions', ['user_id', 'closed_tick']
    )

    op.create_table(
        'game_ledger',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('game_day', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=16), nullable=False),
        sa.Column('amount_krw', sa.BigInteger(), nullable=False),
        sa.Column('ref_type', sa.String(length=16), nullable=True),
        sa.Column('ref_id', sa.Integer(), nullable=True),
        sa.Column('epoch_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_game_ledger_user_id', 'game_ledger', ['user_id'])
    op.create_index('ix_game_ledger_epoch_id', 'game_ledger', ['epoch_id'])


def downgrade() -> None:
    op.drop_table('game_ledger')
    op.drop_table('game_positions')
    op.drop_table('game_wallets')
