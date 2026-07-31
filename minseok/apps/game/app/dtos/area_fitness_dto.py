from dataclasses import dataclass


@dataclass(frozen=True)
class AreaFitnessQuery:

    trdar_code: int
    service_code: str


@dataclass(frozen=True)
class FitnessComponentView:

    key: str
    label: str
    score: float  # 0.0 ~ 1.0
    weight: float


@dataclass(frozen=True)
class DiagnosisView:

    tone: str  # good | warn | bad
    message: str


@dataclass(frozen=True)
class AreaFitnessView:
    """창업 전 미리보기 — 이 상권에 이 업종을 열면 어떻게 되는가.

    `observed_*`는 서울시 상권분석서비스 실데이터, `simulated_*`는 게임 규칙이 만든 값이다
    (game-harness §5-1). 접두사가 곧 출처다.
    """

    trdar_code: int
    trdar_name: str
    service_code: str
    service_name: str
    observed_quarter: int

    # 실데이터
    observed_monthly_sales_amount: int
    observed_store_count: int
    observed_similar_store_count: int
    observed_sales_per_store: int  # 점포당 월매출 — 매출 산식의 기준선
    observed_ticket_price: int  # 객단가 = 매출액 ÷ 매출건수
    observed_closure_rate: float
    observed_operating_months_avg: float

    # 게임 규칙
    fitness: float  # 0.4 ~ 1.6
    total_score: float
    components: tuple[FitnessComponentView, ...]
    simulated_monthly_sales_krw: int  # 점포당 기대매출 × 적합도 (인지도·시설 반영 전)

    diagnoses: tuple[DiagnosisView, ...]
    has_sales: bool
    has_store: bool
