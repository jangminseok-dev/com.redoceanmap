"""상권 데이터 계약 DTO.

허브(hub)가 공개하는 앱 간 협력 계약의 일부. market(스포크)이 채워서 반환하고
chat(스포크)이 소비한다. 원시 수치만 담으며(텍스트 포맷팅은 소비자 관심사),
외부 의존 없는 순수 도메인 객체다.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ServiceCode:
    code: str
    name: str


@dataclass(frozen=True)
class AreaInfo:
    trdar_code: int
    trdar_name: str
    district_name: str
    adm_dong_name: str
    lat: float
    lng: float
    # 원본 좌표(EPSG:5181 중부원점, m 단위) — 반경 질의의 유클리드 거리 계산용.
    # 좌표가 없는 소비자(테스트 스텁 등)는 None — 반경 필터가 성립하지 않는다.
    x_coord: int | None = None
    y_coord: int | None = None


@dataclass(frozen=True)
class AreaSummary:
    areas: list[AreaInfo]
    latest_quarter: int | None
    sales_by_code: dict[int, int]
    # 상권별 월매출 합계의 전년 동분기 대비(%) — 전년 결측·0이면 None.
    # 계절성 지배 데이터라 QoQ 대신 YoY가 "작년보다 올랐나"의 정답 축이다(area_scorer와 동일 논리).
    yoy_by_code: dict[int, float | None] = field(default_factory=dict)


@dataclass(frozen=True)
class AreaOverviewRow:
    """어드민 상권 목록 1행 — 최신 분기 기준 집계. 팩트가 없는 항목은 None."""

    trdar_code: int
    trdar_name: str
    gu_name: str
    dong_name: str
    store_count: int | None
    closure_rate: float | None  # 업종별 팩트의 단순평균 — 어드민 목록 표시 용도
    monthly_sales: int | None


@dataclass(frozen=True)
class AreaInsight:
    """상권 1건의 규칙 기반 해석 문장.

    문장은 market 도메인 서비스(`area_narrator`)가 만들고 허브는 나르기만 한다 —
    `AreaScoreInfo.grade`("우수"/"주의" …)가 이미 같은 방식이다. 원시 수치로 내리면
    임계값 판정이 소비자마다 중복 구현돼, 같은 상권을 지도와 채팅이 다르게 설명하게 된다.
    """

    key: str
    tone: str  # positive | neutral | warning
    text: str


@dataclass(frozen=True)
class AreaScoreComponent:
    """종합점수 컴포넌트 1개 — 50점 = 시도 벤치마크 동률, 0~100."""

    key: str  # 점수 v2: closure_stability / persistence / sales_level
    name: str
    score: float
    value: float
    benchmark: float


@dataclass(frozen=True)
class AreaTrendPoint:
    """분기 1개의 추이 — 값과 변화율(%). 팩트별 결측은 None(market TrendPoint 미러)."""

    year_quarter: int
    monthly_sales: int | None = None
    sales_qoq: float | None = None
    total_floating_pop: int | None = None
    floating_qoq: float | None = None
    sales_yoy: float | None = None
    floating_yoy: float | None = None


@dataclass(frozen=True)
class AreaScoreInfo:
    """상권 1곳의 시도 벤치마크 대비 종합점수(0~100)."""

    total: float
    grade: str  # 우수 / 양호 / 보통 / 주의 / 위험
    components: tuple[AreaScoreComponent, ...]
    # 분기 추이(I-20) — 전문가 질문("분기 추이 데이터 줘")에만 소비. 스코어 슬라이스가
    # 이미 계산하던 것을 나른다(기본값 유지 — 기존 소비자 무손상).
    trend: tuple[AreaTrendPoint, ...] = ()


@dataclass(frozen=True)
class AreaTraitRow:
    """상권 1곳의 성격 원지표 — "직장인 많은 곳 점심 장사" 같은 성격형 질문의 결정론 근거(2026-09-17).

    각 팩트의 최신 분기 값. 금액은 월 환산(원), 점포 수는 유사업종(프랜차이즈 포함).
    매출·점포는 요청한 업종 범위(업종 코드·업종군 접두·전 업종) 합계, 인구·시설은 상권 전체.
    정렬·가중은 소비자 몫 — 값이 없으면 None.
    """

    trdar_code: int
    trdar_name: str
    district_name: str
    dong_name: str
    store_count: int                  # 요청 업종 범위 점포 수
    area_store_count: int             # 상권 전 업종 점포 수(극단값 컷용)
    monthly_sales: int | None
    monthly_sales_count: int | None
    lunch_sales: int | None           # 11~14시
    dinner_sales: int | None          # 17~21시
    night_sales: int | None           # 21~24시 + 00~06시
    weekend_sales: int | None
    weekday_sales: int | None
    age_sales: tuple[int, ...] | None  # 10·20·30·40·50·60+대
    working_pop: int | None
    floating_pop: int | None          # 분기 합계(일평균은 ÷91)
    night_floating_pop: int | None    # 21~24시 + 00~06시 분기 합계
    total_households: int | None
    apartment_households: int | None
    university_count: int | None
    subway_station_count: int | None
    child_facility_count: int | None  # 유치원 + 초등학교


@dataclass(frozen=True)
class AreaRankingInfo:
    """상권 1곳의 랭킹 행 — 조건 질의("폐업률 낮은 N곳") 결정론 라우팅용(1-4).

    market 랭킹 슬라이스와 같은 원칙으로 정렬하지 않고 나른다(정렬은 소비자 몫).
    유동인구 축은 랭킹 집계에 없다 — 소비자는 없는 축을 없다고 고지한다(I-12).
    """

    trdar_code: int
    trdar_name: str
    district_name: str
    dong_name: str
    monthly_sales: int | None      # 원 — 상권 전체 월매출 합계
    store_count: int | None
    sales_per_store: int | None    # 원
    closure_rate: float | None     # %
    change_indicator_name: str | None


@dataclass(frozen=True)
class AreaRawStat:
    """상권 1곳의 원시 통계(특정 업종·분기). 값이 없으면 None, 존재 여부는 has_* 로 표기."""

    # 매출 (EstimatedSales)
    has_sales: bool
    monthly_sales_amount: int | None
    weekday_sales_amount: int | None
    # 점포 (Store)
    has_store: bool
    store_count: int | None  # 유사업종 점포 수(프랜차이즈 포함) — 매출·폐업과 같은 모수
    closure_rate: float | None
    opening_rate: float | None
    franchise_store_count: int | None
    # 유동인구 (FloatingPopulation)
    has_fp: bool
    total_floating_pop: int | None
    age_10_floating_pop: int | None
    age_20_floating_pop: int | None
    age_30_floating_pop: int | None
    age_40_floating_pop: int | None
    age_50_floating_pop: int | None
    age_60_plus_floating_pop: int | None
    time_00_06_floating_pop: int | None
    time_06_11_floating_pop: int | None
    time_11_14_floating_pop: int | None
    time_14_17_floating_pop: int | None
    time_17_21_floating_pop: int | None
    time_21_24_floating_pop: int | None
    # 상권변화 (CommercialChange) — region_*는 상권이 속한 시도의 벤치마크 평균
    has_cc: bool
    change_indicator_name: str | None
    operating_months_avg: float | None
    region_operating_months_avg: float | None
    # --- 아래는 기본값 필드(기존 호출부 무손상용) ---
    # 절대 건수 — 율(%)만으론 소규모 상권에서 노이즈다("3개 중 1개 폐업 = 33%").
    # similar_industry는 경쟁 강도(창업자 직결).
    similar_industry_store_count: int | None = None
    opening_store_count: int | None = None
    closure_store_count: int | None = None
    # 폐업 점포가 버틴 개월 — 운영개월(생존 중)과 짝이 돼야 "얼마 만에 닫는가"가 보인다.
    closure_months_avg: float | None = None
    region_closure_months_avg: float | None = None
    # 판정용 폐업률(2026-09-17) — 최근 4분기 점포 가중(%). 한 분기 closure_rate는 사실 표시용으로만 쓴다.
    closure_rate_4q: float | None = None


@dataclass(frozen=True)
class PermitChurnInfo:
    """인허가 기준 업소 교체 — 최근 창(months) 안의 개업·폐업 수와 현재 영업중 수.

    분기 팩트(`AreaRawStat`의 점포 수)는 "얼마나 있나"만 답한다. 이쪽은 인허가일·폐업일을
    업소 단위로 세므로 "지금 새로 열리고 있나, 빠져나가고 있나"라는 **방향**을 답한다.

    **`active`를 분기 팩트의 점포 수와 비교하지 않는다** — 출처(인허가 대장 vs 상권분석
    서비스)도 집계 기준도 달라 검산이 성립하지 않는다(market 도메인 규칙 그대로 승계).
    상권 매칭이 좌표 근사라 경계 근처는 오차가 있고, 붙은 업소가 없으면 아예 제외된다.

    업소 상호(`recent_openings`)는 나르지 않는다 — 서술에 필요한 건 교체의 방향과 규모이고,
    상호를 주면 모델이 특정 가게를 근거처럼 인용할 여지만 늘어난다.
    """

    months: int    # 집계 창(개월)
    opened: int    # 창 안에 인허가된 업소 수
    closed: int    # 창 안에 폐업한 업소 수
    active: int    # 현재 영업중(창과 무관한 스냅샷)
