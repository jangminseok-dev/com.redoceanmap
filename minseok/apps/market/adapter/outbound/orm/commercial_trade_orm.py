from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class CommercialTradeOrm(Base):
    """국토부 상업업무용 부동산 매매 실거래 — 거래 한 건이 한 행.

    상권 축의 비용 공백(진입 비용)을 메우는 팩트다. 원본(RTMSDataSvcNrgTrade)에 좌표가
    없어 인허가(business_permits)처럼 상권에 직접 붙일 수 없다 — 법정동 시군구코드(sggCd)가
    region의 자치구 코드와 동일 체계(11680=강남구, 2026-08-21 확인)라 **자치구 단위**로
    집계해 상권 서술에 쓴다. umd_nm(법정동명)은 향후 더 좁힐 때를 위해 원문 보존.

    ⚠ 임대(전월세)는 국토부 공개 API에 존재하지 않는다(2026-08-21 확인 —
    RTMSDataSvcNrgRent 등 NO_OPENAPI_SERVICE). 임대료 축은 한국부동산원 R-ONE
    임대동향조사(별도 인증키)가 후속 후보다.

    멱등 규칙: 원본에 거래 고유 ID가 없다 — 적재는 (sgg_cd, 거래 연월) 단위로
    DELETE 후 INSERT 교체한다(collect_commercial_trades.py). 해제 신고(cdealType='O')가
    거래 몇 달 뒤 붙기도 하므로 최근 수개월을 재수집해야 해제가 반영된다.
    """

    __tablename__ = "commercial_trades"
    __table_args__ = (
        # 집계의 지배 패턴: WHERE sgg_cd=? AND deal_date 구간 — 복합 인덱스 하나로 커버
        Index("ix_commercial_trades_sgg_deal", "sgg_cd", "deal_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sgg_cd: Mapped[str] = mapped_column(String(5))       # 법정동 시군구코드 = region 자치구 코드
    sgg_nm: Mapped[str] = mapped_column(String(20))
    umd_nm: Mapped[str] = mapped_column(String(20))      # 법정동명 (역삼동 등)
    jibun: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 일반건물은 마스킹(9**)
    building_type: Mapped[str] = mapped_column(String(8))   # 일반 | 집합
    building_use: Mapped[str | None] = mapped_column(String(30), nullable=True)
    land_use: Mapped[str | None] = mapped_column(String(30), nullable=True)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    build_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    building_ar: Mapped[float] = mapped_column(Float)    # 건물(전용) 면적 ㎡
    deal_amount: Mapped[float] = mapped_column(Float)    # 거래금액(만원)
    deal_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
