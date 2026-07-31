"""상권 수요 프로필 — 창업 시뮬레이션이 쓰는 분포 계약.

`CommercialDataPort`의 `AreaRawStat`과 겹치지 않는다. 저쪽은 **원시 통계 요약**(매출 총액·
점포수·유동인구)이고, 이쪽은 **분포**다 — 매출이 어느 요일·시간대·성별·연령에서 나오는지,
그리고 그 값이 서울 안에서 어느 위치인지.

**절대금액은 두 필드뿐이고 나머지는 비중이다.** 게임 매출은 어차피 게임 규칙으로 스케일되므로
분포만 있으면 되고, 절대값을 전부 내리면 DTO가 50필드가 된다(`estimated_sales`의 측정 컬럼 수).

**백분위는 market이 계산해 준다.** 상권 데이터의 해석은 market 도메인의 일이고(`area_scorer`
선례), 소비자가 저마다 임계값을 정하면 같은 상권을 다르게 설명하게 된다. 그 값으로 무엇을
판정할지는 소비자 몫이다.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class AreaDemandProfile:
    trdar_code: int
    trdar_name: str
    service_code: str
    service_name: str
    year_quarter: int

    # --- 절대값 (객단가·점포당 매출의 재료) ---
    observed_monthly_sales_amount: int
    observed_monthly_sales_count: int
    observed_store_count: int
    observed_similar_store_count: int
    observed_closure_rate: float
    observed_operating_months_avg: float

    # --- 이 상권·업종의 매출 분포 (각 합 1.0, 자료 없으면 전부 0.0) ---
    area_weekday_share: tuple[float, ...]  # 7 — 월·화·수·목·금·토·일
    area_hour_share: tuple[float, ...]  # 6 — 00-06·06-11·11-14·14-17·17-21·21-24
    area_gender_share: tuple[float, ...]  # 2 — 남·여
    area_age_share: tuple[float, ...]  # 6 — 10·20·30·40·50·60+

    # --- 이 상권의 유동인구 분포 (손님이 실제로 지나가는 리듬) ---
    floating_total: int
    floating_hour_share: tuple[float, ...]  # 6
    floating_gender_share: tuple[float, ...]  # 2
    floating_age_share: tuple[float, ...]  # 6

    # --- 업종의 서울 전체 매출 분포 (이 업종이 원래 누구에게 팔리는가) ---
    industry_hour_share: tuple[float, ...]  # 6
    industry_gender_share: tuple[float, ...]  # 2
    industry_age_share: tuple[float, ...]  # 6

    # --- 서울 백분위 (0.0~1.0, 클수록 상위) ---
    saturation_percentile: float  # 유사업종 점포수 ÷ 유동인구 — 높을수록 포화
    closure_rate_percentile: float  # 높을수록 잘 닫는다
    operating_months_percentile: float  # 높을수록 오래 버틴다

    # --- 자료 존재 여부 (없는 축을 0으로 오해하지 않게) ---
    has_sales: bool
    has_store: bool
    has_floating: bool
