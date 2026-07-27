from sqlalchemy import Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from market.adapter.outbound.orm.base_orm import MarketStatMixin


class FacilityOrm(MarketStatMixin, Base):
    """상권별 집객시설 수 — 사람을 끌어오는 앵커(역·학교·병원·백화점).

    서울시가 연 1회만 갱신해 사실상 상권의 준정적 속성이지만, 다른 팩트와 같은 형태로
    전 분기를 적재한다(조회는 최신 1분기만). 3NF 컨벤션에 특례를 만드는 비용이 더 크다.
    """

    __tablename__ = "facility"
    __table_args__ = (
        UniqueConstraint("year_quarter", "trdar_code", name="uq_facility"),
    )

    total_facility_count: Mapped[int] = mapped_column(Integer)
    public_office_count: Mapped[int] = mapped_column(Integer)
    bank_count: Mapped[int] = mapped_column(Integer)
    general_hospital_count: Mapped[int] = mapped_column(Integer)
    hospital_count: Mapped[int] = mapped_column(Integer)
    pharmacy_count: Mapped[int] = mapped_column(Integer)
    kindergarten_count: Mapped[int] = mapped_column(Integer)
    elementary_school_count: Mapped[int] = mapped_column(Integer)
    middle_school_count: Mapped[int] = mapped_column(Integer)
    high_school_count: Mapped[int] = mapped_column(Integer)
    university_count: Mapped[int] = mapped_column(Integer)
    department_store_count: Mapped[int] = mapped_column(Integer)
    supermarket_count: Mapped[int] = mapped_column(Integer)
    theater_count: Mapped[int] = mapped_column(Integer)
    lodging_count: Mapped[int] = mapped_column(Integer)
    airport_count: Mapped[int] = mapped_column(Integer)
    railway_station_count: Mapped[int] = mapped_column(Integer)
    bus_terminal_count: Mapped[int] = mapped_column(Integer)
    subway_station_count: Mapped[int] = mapped_column(Integer)
    bus_stop_count: Mapped[int] = mapped_column(Integer)
