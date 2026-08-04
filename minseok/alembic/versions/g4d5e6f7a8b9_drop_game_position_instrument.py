"""지수 선물 폐지 — game_positions.instrument 제거

Revision ID: g4d5e6f7a8b9
Revises: g3c4d5e6f7a8
Create Date: 2026-08-04

`instrument`는 선물(FUTURES)과 주식(STOCK)을 한 테이블에서 가르려고 `d5e6f7a8b9c0`이
넣은 컬럼이다. 선물 게임이 폐지돼(프론트 `1102965`) 값이 STOCK 하나뿐이 되므로 지운다 —
남겨두면 코드가 영원히 참이 될 수 없는 분기를 안고 간다.

**제거 전 실측(2026-08-04)**: `game_positions` 10행이 **전부 STOCK**이고 미청산 0건,
`game_limit_orders` 0행. 프론트 커밋이 경고한 "미정산 선물 포지션이 영영 정산되지 않는다"는
상황은 애초에 만들어진 적이 없어 **강제 정산 스크립트가 필요 없었다.** 선물 포지션이
한 건이라도 있었다면 이 마이그레이션보다 정산이 먼저였다.

되돌리려면 downgrade가 컬럼을 다시 만든다(기본값 STOCK) — 선물 데이터는 없었으므로
복원할 값도 없다.
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "g4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "g3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("game_positions", "instrument")


def downgrade() -> None:
    op.add_column(
        "game_positions",
        sa.Column("instrument", sa.String(8), nullable=False, server_default="STOCK"),
    )
