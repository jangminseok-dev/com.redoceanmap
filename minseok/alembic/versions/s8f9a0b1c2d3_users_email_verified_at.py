"""users.email_verified_at — 이메일 인증 시각(알림 메일 수신 조건)

인증된 주소로만 알림 메일을 보낸다(2026-09-21 — QA 계정으로 나간 알림의 반송 안내가 발신 계정 받은편지함을 채운 사고).
가입·로그인은 막지 않는다. 기존 회원은 NULL(미인증)로 시작한다 — 소급 인증은 하지 않는다.

Revision ID: s8f9a0b1c2d3
Revises: r7e8f9a0b1c2
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "s8f9a0b1c2d3"
down_revision: Union[str, Sequence[str], None] = "r7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "email_verified_at")
