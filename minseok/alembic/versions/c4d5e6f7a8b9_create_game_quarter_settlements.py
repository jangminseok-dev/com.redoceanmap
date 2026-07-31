"""게임 분기 결산.

일별 매출은 저장하지 않지만 결산은 저장한다 — 분기 손익이 지갑에 반영되는 것은
캐시가 아니라 게임 규칙상 실재하는 사건이다.

(store_id, game_quarter) 유니크가 이중 정산을 DB에서 막는다. 결산은 지연 실행이라
조회가 잦고, 멱등성이 곧 정확성이다.

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'game_quarter_settlements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('store_id', sa.Integer(), nullable=False),
        sa.Column('game_quarter', sa.Integer(), nullable=False),
        sa.Column('days_counted', sa.Integer(), nullable=False),
        sa.Column('total_sales_krw', sa.BigInteger(), nullable=False),
        sa.Column('total_rent_krw', sa.BigInteger(), nullable=False),
        sa.Column('total_labor_krw', sa.BigInteger(), nullable=False),
        sa.Column('total_cogs_krw', sa.BigInteger(), nullable=False),
        sa.Column('total_utility_krw', sa.BigInteger(), nullable=False),
        sa.Column('profit_krw', sa.BigInteger(), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('epoch_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['game_stores.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('store_id', 'game_quarter', name='uq_game_quarter_settlements'),
    )
    op.create_index(
        'ix_game_quarter_settlements_store_id', 'game_quarter_settlements', ['store_id']
    )
    op.create_index(
        'ix_game_quarter_settlements_epoch_id', 'game_quarter_settlements', ['epoch_id']
    )
    op.create_index(
        'ix_game_quarter_settlements_store',
        'game_quarter_settlements',
        ['store_id', 'game_quarter'],
    )


def downgrade() -> None:
    op.drop_table('game_quarter_settlements')
