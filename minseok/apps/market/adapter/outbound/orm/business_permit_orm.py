from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class BusinessPermitOrm(Base):
    """지방행정 인허가 업소 — 서울 열린데이터광장 LOCALDATA_* 원본의 업소 단위 이력.

    기존 상권 팩트(`store`)는 분기별 **점포 수**라 "지난달 어떤 가게가 새로 열었나"를 답할 수
    없다. 이 테이블은 업소 한 곳이 한 행이고 인허가일·폐업일을 그대로 들고 있어 임의 기간의
    개업·폐업을 셀 수 있다.

    상권 매칭(`trdar_code`)은 적재 시점에 좌표로 계산해 굳힌다 — 원본 X/Y가 trade_area와 같은
    EPSG:5174라 변환 없이 거리로 붙는다. 상권 폴리곤이 없어 면적에서 원으로 근사하므로
    **경계 근처는 오차가 있다**(2026-07-30 게이트 실측 매칭률 54.5%). 반경 밖이면 NULL로 둔다 —
    서울 전역의 업소 중 상권에 속하지 않는 것이 정상적으로 존재한다.
    """

    __tablename__ = "business_permits"
    __table_args__ = (
        # 관리번호는 개방서비스 안에서만 유일하다 — 서비스ID와 함께 묶어야 음식점/휴게음식점이
        # 같은 번호를 써도 충돌하지 않는다. 재수집 멱등의 근거이기도 하다.
        UniqueConstraint("service_id", "mgt_no", name="uq_business_permits_service_mgt"),
        # 상권 상세가 "최근 개업/폐업"을 뽑는 경로 — 상권으로 좁히고 날짜로 정렬한다.
        Index("ix_business_permits_trdar_permit", "trdar_code", "permit_date"),
        Index("ix_business_permits_trdar_close", "trdar_code", "close_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[str] = mapped_column(String(24))  # 예: LOCALDATA_072404(일반음식점)
    mgt_no: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(200))  # 상호(BPLCNM)
    category: Mapped[str | None] = mapped_column(String(60), nullable=True)  # 업태(UPTAENM)
    state: Mapped[str] = mapped_column(String(20), default="")  # 영업상태명(TRDSTATENM)

    # 인허가일은 거의 항상 있고 폐업일은 영업중이면 없다. 둘 다 원본이 공백 문자열을 섞어 보낸다.
    permit_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    close_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    x_coord: Mapped[float | None] = mapped_column(Float, nullable=True)
    y_coord: Mapped[float | None] = mapped_column(Float, nullable=True)
    trdar_code: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("trade_area.code"), nullable=True, index=True
    )

    address: Mapped[str | None] = mapped_column(String(300), nullable=True)  # 지번주소(SITEWHLADDR)
    site_area: Mapped[float | None] = mapped_column(Float, nullable=True)  # 영업장 면적(㎡)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
