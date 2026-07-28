"""랭체인 시멘틱 게이트웨이(ROM 2.0)의 대화 세션·턴 테이블.

허브가 소유하는 첫 ORM이다(비전과 같은 '허브 직접 소유 기능'). chat 스포크의
conversations/messages와 분리한 이유는 소유 앱이 다르고, 턴마다 시멘틱 분류 결과
(destination)를 함께 남겨 분기별 품질을 사후에 갈라 보기 위해서다.

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd7e8f9a0b1c2'
down_revision: Union[str, Sequence[str], None] = 'c6d7e8f9a0b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'langchain_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        # users를 FK로 참조하지 않는다 — 앱 간 DB 결합 회피(conversations와 같은 판단)
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_langchain_sessions_user_id'), 'langchain_sessions', ['user_id']
    )

    op.create_table(
        'langchain_turns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=16), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('destination', sa.String(length=16), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False
        ),
        sa.ForeignKeyConstraint(['session_id'], ['langchain_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_langchain_turns_session_id'), 'langchain_turns', ['session_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_langchain_turns_session_id'), table_name='langchain_turns')
    op.drop_table('langchain_turns')
    op.drop_index(op.f('ix_langchain_sessions_user_id'), table_name='langchain_sessions')
    op.drop_table('langchain_sessions')
