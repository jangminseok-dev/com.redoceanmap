"""add user kakao identity

모바일 카카오 로그인 — 카카오 회원번호를 유저 식별자로 추가한다.
이메일은 카카오 선택 동의 항목이라 없을 수 있으므로 NOT NULL을 푼다(UNIQUE는 유지 —
Postgres는 NULL 중복을 허용한다). 기존 이메일/비밀번호 계정은 그대로 동작한다.
유저는 플랫폼과 무관하게 하나다 — 분리되는 것은 세션이지 계정이 아니다.

Revision ID: c9d0e1f2a3b4
Revises: d5e6f7a8b9c0
Create Date: 2026-08-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, Sequence[str], None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('kakao_id', sa.BigInteger(), nullable=True))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint('uq_users_kakao_id', 'users', ['kakao_id'])
    op.alter_column('users', 'email', existing_type=sa.String(255), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # 이메일이 비어 있는 카카오 전용 계정이 있으면 NOT NULL 복원은 실패한다 — 의도된 안전장치다.
    op.alter_column('users', 'email', existing_type=sa.String(255), nullable=False)
    op.drop_constraint('uq_users_kakao_id', 'users', type_='unique')
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'kakao_id')
