"""game 스포크 폐기 — 테이블 11개 drop (GAME_SUNSET_PAPER_TRADING_PLAN_2026-09 2단계)

모의투자 게임·상권 창업 시뮬레이터를 저장소에서 제거했다(태그 `game-archive`에 코드 보존).
남아 있던 데이터는 테스트 계정 3명분(지갑 3·포지션 15·가게 3)이며 04:00 백업으로 복원 가능하다.
앞선 game 리비전 8개는 체인 무결성 때문에 남긴다.

downgrade는 지원하지 않는다 — 스키마만 되살려도 결정론 엔진·게임 규칙 코드가 없어 의미가 없다.

Revision ID: o4b5c6d7e8f9
Revises: n3a4b5c6d7e8
Create Date: 2026-09-08
"""
from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "o4b5c6d7e8f9"
down_revision: Union[str, Sequence[str], None] = "n3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# FK 피참조 테이블이 뒤에 오도록 정렬 (comments→posts, limit_orders→positions, decisions·settlements→stores)
_TABLES = (
    "game_community_comments",
    "game_community_reports",
    "game_community_posts",
    "game_limit_orders",
    "game_store_decisions",
    "game_quarter_settlements",
    "game_stores",
    "game_ledger",
    "game_positions",
    "game_price_interventions",
    "game_wallets",
)


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table}")


def downgrade() -> None:
    raise NotImplementedError("game 테이블은 복구하지 않는다 — 백업(scripts/backup_db.sh)으로 복원한다")
