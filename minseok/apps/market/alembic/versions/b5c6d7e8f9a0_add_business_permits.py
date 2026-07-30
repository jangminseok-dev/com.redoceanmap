"""add business permits (지방행정 인허가 업소)

기존 `store` 팩트는 분기별 **점포 수**라 "지난달 어떤 가게가 새로 열었나"를 못 답한다.
업소 한 곳이 한 행이고 인허가일·폐업일을 그대로 들고 있어 임의 기간의 개업·폐업을 센다.

출처는 서울 열린데이터광장 LOCALDATA_072404(일반음식점)·LOCALDATA_072405(휴게음식점) —
localdata.go.kr은 이 호스트에서 TCP 443이 닿지 않아 서울시 API로 받는다(기존 상권 수집과 같은 창구).
적재는 scripts/collect_business_permits.py.

Revision ID: b5c6d7e8f9a0
Revises: f4e5d6c7b8a9
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "b5c6d7e8f9a0"
down_revision: Union[str, Sequence[str], None] = "f4e5d6c7b8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "business_permits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("service_id", sa.String(length=24), nullable=False),
        sa.Column("mgt_no", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("permit_date", sa.Date(), nullable=True),
        sa.Column("close_date", sa.Date(), nullable=True),
        sa.Column("x_coord", sa.Float(), nullable=True),
        sa.Column("y_coord", sa.Float(), nullable=True),
        # 상권 매칭 실패는 정상이다(서울 전역 업소 중 상권 밖이 존재) — nullable + FK.
        sa.Column("trdar_code", sa.Integer(), nullable=True),
        sa.Column("address", sa.String(length=300), nullable=True),
        sa.Column("site_area", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["trdar_code"], ["trade_area.code"]),
        sa.PrimaryKeyConstraint("id"),
        # 관리번호는 개방서비스 안에서만 유일 — 재수집 멱등(ON CONFLICT)의 근거다.
        sa.UniqueConstraint("service_id", "mgt_no", name="uq_business_permits_service_mgt"),
    )
    op.create_index("ix_business_permits_trdar_code", "business_permits", ["trdar_code"])
    # 상권 상세의 "최근 개업/폐업" 조회 경로 — 상권으로 좁힌 뒤 날짜 정렬.
    op.create_index("ix_business_permits_trdar_permit", "business_permits",
                    ["trdar_code", "permit_date"])
    op.create_index("ix_business_permits_trdar_close", "business_permits",
                    ["trdar_code", "close_date"])


def downgrade() -> None:
    op.drop_index("ix_business_permits_trdar_close", table_name="business_permits")
    op.drop_index("ix_business_permits_trdar_permit", table_name="business_permits")
    op.drop_index("ix_business_permits_trdar_code", table_name="business_permits")
    op.drop_table("business_permits")
