"""drop redundant single-column trdar_code indexes

`ix_<fact>_trdar_code`는 직전 리비전이 만든 `ix_<fact>_trdar_quarter`
(`trdar_code, year_quarter`)의 **엄격한 접두사**라 잉여다. 남겨두면 적재 INSERT마다
9개를 더 유지해야 한다(팩트 합계 226만 행, 분기마다 증가).

`ix_<fact>_year_quarter`는 유지한다 — `area_ranking`의 `WHERE year_quarter = ?`와
시도 벤치마크 캐시의 `max(year_quarter)` index-only scan이 이걸 쓴다.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""
from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

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
        op.drop_index(f"ix_{table}_trdar_code", table_name=table)


def downgrade() -> None:
    for table in _FACTS:
        op.create_index(f"ix_{table}_trdar_code", table, ["trdar_code"])
