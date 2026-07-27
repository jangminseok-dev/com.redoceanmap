"""add (trdar_code, year_quarter DESC) composite index on all facts

팩트 조회의 지배적 패턴은 `WHERE trdar_code=? ORDER BY year_quarter DESC LIMIT n`인데,
기존 인덱스로는 이 모양을 한 번에 만족시키지 못했다:
- `ix_*_trdar_code`는 단일 컬럼이라 정렬을 못 준다
- `uq_*`는 선두가 `year_quarter`라 trdar 필터에 쓸 수 없다(역방향 전체 스캔으로 샌다)

2021~2024 백필로 팩트당 분기가 1~4개에서 20~28개로 늘면서 이 패턴의 비용이 분기 수에
비례해 커졌다. 상권당 행수도 함께 늘어(store는 상권당 평균 927행) 지금 갚아둔다.

Revision ID: f3e4d5c6b7a8
Revises: 9a1b2c3d4e5f
"""
from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "f3e4d5c6b7a8"
down_revision: Union[str, Sequence[str], None] = "9a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 팩트 9종 — 전부 (trdar_code, year_quarter) 그레인
_FACTS = (
    "estimated_sales",
    "store",
    "floating_population",
    "resident_population",
    "working_population",
    "consumption",
    "apartment",
    "commercial_change",
    "facility",
)


def upgrade() -> None:
    for table in _FACTS:
        op.create_index(
            f"ix_{table}_trdar_quarter",
            table,
            ["trdar_code", "year_quarter"],
            postgresql_ops={"year_quarter": "DESC"},
        )


def downgrade() -> None:
    for table in _FACTS:
        op.drop_index(f"ix_{table}_trdar_quarter", table_name=table)
