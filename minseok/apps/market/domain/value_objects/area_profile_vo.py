from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SalesMix:
    """최신 분기 매출 구조 분해 — 금액은 원 단위. 키 순서는 노출 순서와 같다."""

    year_quarter: int
    weekday_amount: int
    weekend_amount: int
    by_day: dict[str, int]     # mon..sun
    by_time: dict[str, int]    # t00_06..t21_24
    by_gender: dict[str, int]  # male, female
    by_age: dict[str, int]     # age10..age60Plus
    monthly_count: int
    monthly_amount: int = 0    # 월 총매출 — 객단가 계산용(0이면 성별 합으로 폴백)
    # 건수 축 — 금액/건수로 "언제 누가 얼마씩 쓰는가"(객단가)를 낸다. 금액만으론
    # 매출 큰 층이 '많이 오는 층'인지 '비싸게 쓰는 층'인지 구분할 수 없다.
    weekday_count: int = 0
    weekend_count: int = 0
    count_by_age: dict[str, int] | None = None  # age10..age60Plus


@dataclass(frozen=True)
class FloatingRhythm:
    """최신 분기 통행 리듬 — 요일 7개를 주중/주말로 접어 매출 리듬과 대조한다.

    요일 7개를 그대로 노출하면 화면·스키마가 하나 더 늘지만, 실제로 값을 하는 건
    "통행은 주말인데 매출은 평일" 같은 교차 신호 하나다.
    """

    year_quarter: int
    weekday_pop: int  # 월~금 합
    weekend_pop: int  # 토+일


@dataclass(frozen=True)
class FacilityProfile:
    """최신 분기 집객시설 — 사람을 끌어오는 앵커만 추린다.

    원천은 20종이지만 창업 판단에 실제로 값하는 건 '외부 유입 동선'을 만드는 몇 개다.
    20개를 다 노출하면 숫자 나열이 된다.
    """

    year_quarter: int
    total: int
    subway_stations: int
    bus_stops: int
    universities: int
    department_stores: int
    hospitals: int  # 종합병원 + 일반병원


@dataclass(frozen=True)
class AgeBand:
    band: str  # "10".."60+"
    male: int
    female: int


@dataclass(frozen=True)
class ResidentProfile:
    year_quarter: int
    total: int
    by_age: list[AgeBand]
    total_households: int
    apartment_households: int


@dataclass(frozen=True)
class WorkingProfile:
    year_quarter: int
    total: int
    by_age: list[AgeBand]


@dataclass(frozen=True)
class ApartmentProfile:
    year_quarter: int
    complex_count: int
    avg_price: int  # 원
    avg_area: int   # ㎡


@dataclass(frozen=True)
class SpendingCategory:
    key: str
    label: str
    amount: float  # 원


@dataclass(frozen=True)
class SpendingProfile:
    year_quarter: int
    monthly_avg_income: float | None  # 원
    total_expenditure: float | None   # 원
    by_category: list[SpendingCategory]  # 금액 내림차순, 결측 제외
