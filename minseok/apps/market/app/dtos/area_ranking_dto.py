from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AreaRankingQuery:
    """상권 랭킹 조회 입력 — 전부 선택. 미지정이면 서울 전 상권."""

    district_name: str | None = None
    division_code: str | None = None  # 골목/발달/전통시장/관광특구
    service_code: str | None = None   # 지정 시 해당 업종만 집계("카페 하기 좋은 상권")
    change_indicator: str | None = None  # 상권변화지표명(다이나믹/상권확장/상권축소/정체) — 지정 시 해당 분류만
    dong_name: str | None = None      # 행정동명 (예: 성수동) — gu와 같은 결의 필터(I-3)


@dataclass(frozen=True)
class AreaRankingRow:
    """상권 1곳의 랭킹 행 — 팩트가 없는 축은 None(정렬은 소비자 몫)."""

    trdar_code: int
    trdar_name: str
    district_name: str
    dong_name: str
    division_code: str
    division_name: str
    lat: float
    lng: float
    monthly_sales: int | None
    store_count: int | None
    # 규모 큰 상권이 항상 좋은 게 아니다 — 점포당 매출이 "돈이 되는가"의 단일 최고 지표
    sales_per_store: int | None
    sales_qoq: float | None       # 직전 분기 대비 %, 직전 분기 결측이면 None
    closure_rate: float | None
    area_size: float | None  # ㎡ — 밀도 정규화용
    change_indicator_name: str | None = None  # 상권변화지표명 — 변화 팩트 결측이면 None(I-1)


@dataclass(frozen=True)
class DongRollupRow:
    """행정동 1개의 롤업 집계 — 상권 단위가 못 답하는 "동 전체" 질문용(I-3).

    QoQ는 동 합계 기준이되, 소속 상권 중 하나라도 직전 분기 매출이 결측이면 None —
    커버리지가 다른 분기를 나누면 허위 성장률이 된다.
    """

    district_name: str
    dong_name: str
    area_count: int
    monthly_sales: int | None
    store_count: int | None
    sales_per_store: int | None
    sales_qoq: float | None


@dataclass(frozen=True)
class ServiceOption:
    code: str
    name: str


@dataclass(frozen=True)
class AreaRankingView:
    year_quarter: int | None  # 집계 기준 분기(데이터 없으면 None)
    rows: list[AreaRankingRow]
    # 이 엔드포인트 자신의 필터 어휘 — 목록 하나 때문에 라우터를 새로 만들지 않는다
    services: list[ServiceOption]
    # 행정동 롤업(I-3) — 이미 받은 행의 재집계라 추가 쿼리가 없다. 필터(gu·업종·변화지표)를
    # 그대로 반영한 부분집합 위에서 계산된다.
    dong_rollup: list[DongRollupRow] = field(default_factory=list)


# ── 쇼케이스 — 비로그인 첫 화면용 공개 뷰 ────────────────────────────────
# 랭킹과 같은 원자재를 쓰지만 **필드를 의도적으로 줄인다**. 인증 없이 나가는
# 응답이라 "필요한 것만" 원칙을 계약 수준에서 못박는다.
#   lat/lng      — 지도 없는 화면에 용도가 없다
#   monthly_sales — "이 동네가 얼마 번다"로 오독된다
#   closure_rate  — 업종·표본 맥락 없이 내면 특정 상권에 '위험' 낙인이 찍힌다
#   sales_qoq     — %가 붙는 순간 "추세 → 미래"로 읽힌다(예측 안 한다는 정책 위반)


@dataclass(frozen=True)
class AreaShowcaseRow:
    """쇼케이스 카드 1장 — 공개해도 되는 6필드만."""

    trdar_code: int
    trdar_name: str
    district_name: str
    division_name: str  # 상위가 왜 시장인지를 카드 스스로 설명하는 라벨
    sales_per_store: int
    store_count: int  # 모수 없는 점포당 매출은 정직하지 않다 — 항상 동행한다


@dataclass(frozen=True)
class DivisionMedian:
    """상권유형별 점포당 매출 중앙값 — 상위 카드의 극단값을 읽는 자.

    1위가 점포당 월 19.6억(도매시장)인데 맥락이 없으면 "창업하면 19억 번다"로
    읽힌다. 유형별 중앙값을 같이 내서 그게 얼마나 바깥값인지 보이게 한다.
    """

    division_name: str
    area_count: int
    median_sales_per_store: int


@dataclass(frozen=True)
class AreaShowcaseView:
    year_quarter: int | None   # 집계 기준 분기(= 매출 팩트의 최신 분기)
    quarter_from: int | None   # 매출·점포 보유 시작 분기 — "몇 분기 쌓였는가"
    area_count: int            # 서울 전체 상권 수(팩트 없는 상권 포함)
    min_store_count: int       # 컷오프 — 프론트가 숫자를 하드코딩하지 않게 실어 보낸다
    rows: list[AreaShowcaseRow]
    division_medians: list[DivisionMedian]
