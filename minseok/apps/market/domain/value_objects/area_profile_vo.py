from __future__ import annotations

from dataclasses import dataclass
from datetime import date


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
    count_by_age: dict[str, int] | None = None     # age10..age60Plus
    count_by_day: dict[str, int] | None = None     # mon..sun
    count_by_time: dict[str, int] | None = None    # t00_06..t21_24
    count_by_gender: dict[str, int] | None = None  # male, female


@dataclass(frozen=True)
class ServiceRank:
    """상권 안 업종 1개의 성적 — "이 자리에서 뭐가 되나".

    estimated_sales가 상권 × 업종으로 적재돼 있는데 지금까지 매출 최대 업종 1개만
    쓰고 나머지(중앙 11개·최대 53개)를 버렸다.
    """

    code: str
    name: str
    monthly_sales: int
    store_count: int | None
    sales_per_store: int | None   # "돈이 되는가"의 단일 최고 지표
    sales_qoq: float | None
    closure_rate: float | None


@dataclass(frozen=True)
class FloatingRhythm:
    """최신 분기 통행 리듬 — 요일 7개를 주중/주말로 접어 매출 리듬과 대조한다.

    요일 7개를 그대로 노출하면 화면·스키마가 하나 더 늘지만, 실제로 값을 하는 건
    "통행은 주말인데 매출은 평일" 같은 교차 신호 하나다.
    """

    year_quarter: int
    weekday_pop: int  # 월~금 합
    weekend_pop: int  # 토+일
    # 성별 통행 — 매출 성별 구성과 맞대면 "지나가는 사람"과 "사는 사람"의 차이가 나온다
    male_pop: int = 0
    female_pop: int = 0


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
    # 상권 성격 축 — 개별 13종을 그대로 세지 않고 "왜 오는가"가 같은 것끼리 묶는다.
    gateway: int = 0      # 철도역 + 버스터미널 + 공항 — 서울 밖에서 오는 광역 유입
    schools: int = 0      # 유치원 + 초 + 중 + 고 — 학생·학부모 동선
    nightlife: int = 0    # 극장 + 숙박 — 밤·주말 체류
    convenience: int = 0  # 은행 + 약국 + 슈퍼마켓 + 관공서 — 생활 밀착 동선


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
    # 분포 — 평균 하나로는 "고가 단지가 섞인 상권"과 "고르게 중저가인 상권"을 구분할 수 없다.
    # 원천의 빈칸은 결측이 아니라 "그 구간 세대 없음"이다(전 행이 최소 한 구간을 보유) — 0으로 읽는다.
    price_bands: dict[str, int] | None = None  # under1b·b1·b2·b3·b4·b5·over6b
    area_bands: dict[str, int] | None = None   # under66·a66·a99·a132·a165


@dataclass(frozen=True)
class PermitOpening:
    """개업(또는 폐업) 업소 한 건 — 상호가 붙어야 "무엇이 열렸나"가 읽힌다."""

    name: str
    category: str | None  # 업태(한식·커피숍 등)
    happened_on: date


@dataclass(frozen=True)
class PermitChurn:
    """인허가 기준 업소 교체 — 분기 팩트(`store`)가 못 주는 '업소 단위·임의 기간' 축.

    `store`는 분기별 점포 **수**라 "지난달 무엇이 새로 열었나"를 못 답한다. 여기서는
    인허가일·폐업일을 그대로 세므로 최근 12개월 같은 임의 창을 잡을 수 있다.

    **영업중 업소 수(`active`)는 `store`의 점포 수와 다르다** — 출처(인허가 대장 vs 상권분석
    서비스)도 집계 기준도 달라서, 둘을 같은 화면에서 비교하거나 검산하지 않는다.
    """

    months: int             # 집계 창(개월)
    opened: int             # 창 안에 인허가된 업소 수
    closed: int             # 창 안에 폐업한 업소 수
    active: int             # 현재 영업중(창과 무관한 스냅샷)
    recent_openings: list[PermitOpening]  # 최신순 상위 몇 건
    recent_closings: list[PermitOpening]


@dataclass(frozen=True)
class AssetPrice:
    """자치구 상가·업무용 매매 평단가 — 상권 진입 비용 축(국토부 실거래, 집합건물 호실 기준).

    상권 단위가 아니라 **자치구 단위**다 — 원본에 좌표가 없어 상권에 직접 붙지 않는다.
    같은 구의 모든 상권이 같은 값을 받으므로 문장에 구 이름을 명시해 좌표계를 드러낸다.
    임대료가 아니라 매매가다(임대 실거래는 공개 API에 없다, 2026-08-21 확인).
    """

    gu_name: str
    months: int                    # 집계 창(개월)
    n: int                         # 창 안의 거래 건수(집합건물)
    median_price_per_m2: float     # 만원/㎡ 중앙값
    seoul_rank: int                # 서울 자치구 중 몇 번째로 높은가(1=최고가)
    seoul_total: int               # 집계된 자치구 수

    # 전년 대비(YoY)는 싣지 않는다 — 자치구 중앙 평단가의 YoY는 실측 ±130%까지 튀는
    # **구성 잡음**(고가 신축 분양 유무로 믹스가 바뀐다)이라 "가격이 올랐다"가 허위가 된다.


@dataclass(frozen=True)
class StartupCost:
    """공정위 가맹 정보공개서 기준 업종별 창업비용(원) — 상권 축의 비용 공백을 메우는 팩트(B7).

    가맹금·교육비·보증금·기타의 합계 **중앙값**이라 점포 임대료·권리금은 없다 — 문장이 한계를 함께 말한다.
    업종은 공정위 중분류(커피·치킨·주점 …)이며 서울시 업종명과 다르다 — 매핑은 narrator가 소유한다.
    """

    industry_name: str
    year: int
    total_amount: int
    brand_count: int | None


@dataclass(frozen=True)
class ChangeProfile:
    """상권변화지표 — 운영·폐업 영업개월을 시도 평균과 비교한 2×2 분류(서울시 1급 축).

    지표 이름(다이나믹/상권확장/상권축소/정체)은 원천 차원 테이블 값 그대로다.
    해석 문장은 narrator가 만든다 — 값은 있는데 이름만 노출되던 축(I-1).
    """

    year_quarter: int
    indicator_name: str                     # 다이나믹 | 상권확장 | 상권축소 | 정체
    operating_months: float | None          # 이 상권 생존 점포 평균 영업개월
    closure_months: float | None            # 폐업 점포가 버틴 평균 영업개월
    region_operating_months: float | None   # 시도(서울) 벤치마크
    region_closure_months: float | None


@dataclass(frozen=True)
class SpendingCategory:
    key: str
    label: str
    amount: float  # 원


@dataclass(frozen=True)
class SpendingProfile:
    year_quarter: int
    monthly_avg_income: float | None  # 원 — 서울시가 2020년부터 제공 중단(2019년 분기에만 존재)
    total_expenditure: float | None   # 원
    by_category: list[SpendingCategory]  # 금액 내림차순, 결측 제외
    # 소득 구간(1~10)과 서울 내 상대 위치 — 금액이 끊긴 뒤 남은 유일한 소득 신호다.
    # 절대 구간 숫자("6구간")는 사용자에게 의미가 없어 백분위와 짝으로만 쓴다.
    income_band: int | None = None
    income_percentile: float | None = None  # 0~1, 이 상권보다 낮은 구간 상권의 비율
