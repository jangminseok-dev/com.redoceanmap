"""add facility fact (집객시설-상권)

상권별 집객시설 수 — 사람을 끌어오는 앵커(역·학교·병원·백화점).
서울 상권분석서비스 표준 세트 중 유일하게 미보유였던 팩트다. 포털에 파일이 없어
OpenAPI(VwsmTrdarFcltyQq)로 받는다 — scripts/fetch_seoul_facility.py.

Revision ID: 9a1b2c3d4e5f
Revises: 8d6efce2a41b
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "9a1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "8d6efce2a41b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COUNT_COLUMNS = (
    "total_facility_count",
    "public_office_count",
    "bank_count",
    "general_hospital_count",
    "hospital_count",
    "pharmacy_count",
    "kindergarten_count",
    "elementary_school_count",
    "middle_school_count",
    "high_school_count",
    "university_count",
    "department_store_count",
    "supermarket_count",
    "theater_count",
    "lodging_count",
    "airport_count",
    "railway_station_count",
    "bus_terminal_count",
    "subway_station_count",
    "bus_stop_count",
)


def upgrade() -> None:
    op.create_table(
        "facility",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("year_quarter", sa.Integer(), nullable=False),
        sa.Column("trdar_code", sa.Integer(), nullable=False),
        *(sa.Column(name, sa.Integer(), nullable=False) for name in _COUNT_COLUMNS),
        sa.ForeignKeyConstraint(["trdar_code"], ["trade_area.code"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("year_quarter", "trdar_code", name="uq_facility"),
    )
    op.create_index(op.f("ix_facility_year_quarter"), "facility", ["year_quarter"])
    op.create_index(op.f("ix_facility_trdar_code"), "facility", ["trdar_code"])


def downgrade() -> None:
    op.drop_index(op.f("ix_facility_trdar_code"), table_name="facility")
    op.drop_index(op.f("ix_facility_year_quarter"), table_name="facility")
    op.drop_table("facility")
