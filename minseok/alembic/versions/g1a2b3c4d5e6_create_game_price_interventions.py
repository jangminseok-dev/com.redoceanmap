"""게임 관리자 주가 개입 테이블 + game:write 권한

Revision ID: g1a2b3c4d5e6
Revises: c9d0e1f2a3b4
Create Date: 2026-08-03

주가는 저장하지 않는 게임이지만(game-harness §4-2) 관리자의 의도만은 난수에서 유도할 수
없어 이 테이블 하나를 둔다. `from_tick` 이후에만 효력이 있어 과거는 바뀌지 않는다.
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "g1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PERMISSIONS = [
    ("game:write", "게임 운영 — 자본 지급·주가 개입"),
    ("game:read", "게임 운영 조회 — 지갑·개입 이력"),
]


def upgrade() -> None:
    op.create_table(
        "game_price_interventions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("epoch_id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=8), nullable=False),
        sa.Column("target", sa.String(length=32), nullable=False),
        sa.Column("target_name", sa.String(length=32), nullable=False),
        sa.Column("from_tick", sa.Integer(), nullable=False),
        sa.Column("shock_pct", sa.Float(), nullable=False),
        sa.Column("drift_pct_per_day", sa.Float(), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("headline", sa.String(length=120), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_game_price_interventions_epoch_id", "game_price_interventions", ["epoch_id"]
    )
    # 조회 패턴이 항상 (에포크, 창 안의 틱)이라 복합으로 잡는다
    op.create_index(
        "ix_game_price_interventions_epoch_tick",
        "game_price_interventions",
        ["epoch_id", "from_tick"],
    )

    for code, description in _PERMISSIONS:
        op.execute(
            sa.text(
                "INSERT INTO permissions (code, description) "
                "SELECT :code, :description "
                "WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = :code)"
            ).bindparams(code=code, description=description)
        )
        op.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT r.id, p.id FROM roles r, permissions p "
                "WHERE r.code = 'admin' AND p.code = :code "
                "AND NOT EXISTS (SELECT 1 FROM role_permissions rp "
                "WHERE rp.role_id = r.id AND rp.permission_id = p.id)"
            ).bindparams(code=code)
        )


def downgrade() -> None:
    for code, _ in _PERMISSIONS:
        op.execute(
            sa.text(
                "DELETE FROM role_permissions WHERE permission_id = "
                "(SELECT id FROM permissions WHERE code = :code)"
            ).bindparams(code=code)
        )
        op.execute(sa.text("DELETE FROM permissions WHERE code = :code").bindparams(code=code))
    op.drop_index("ix_game_price_interventions_epoch_tick", "game_price_interventions")
    op.drop_index("ix_game_price_interventions_epoch_id", "game_price_interventions")
    op.drop_table("game_price_interventions")
