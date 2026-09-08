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
    """입지 적합도 — 이 상권에 이 업종이 맞는 자리인가.

    `observed_*`는 서울시 상권분석서비스 실데이터다. 창업비용·임대료 같은 가정치는 없다
    (실데이터가 들어오면 별도 슬라이스 — ROADMAP B4).
    """

    trdar_code: int
    trdar_name: str
    service_code: str
    service_name: str
    year_quarter: int

    observed_monthly_sales_amount: int
    observed_store_count: int
    observed_similar_store_count: int
    observed_sales_per_store: int  # 점포당 월매출
    observed_ticket_price: int  # 객단가 = 매출액 ÷ 매출건수
    observed_closure_rate: float
    observed_operating_months_avg: float

    total_score: float  # 0.0 ~ 1.0
    components: tuple[FitnessComponentView, ...]
    diagnoses: tuple[DiagnosisView, ...]
    has_sales: bool
    has_store: bool
