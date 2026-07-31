"""창업 경제 계수 — **이 파일이 유일한 소유자다** (game-harness §5-3).

임대료·인건비·원가는 **공개 데이터가 없다.** ROADMAP도 "비용 측면(임대료 부재)"을 3대 공백으로
적어뒀다. 그래서 게임 규칙으로 산정하되, 실데이터에 앵커를 걸고 **출처를 값에 붙여 다닌다.**

실데이터가 확보되면 `source`를 `"observed"`로 바꾸는 것만으로 UI의 가정치 배지가 사라진다 —
그것이 "계수만 교체 가능한 구조"의 실제 구현이다.

이 파일 밖에서 임대료·인건비·원가 리터럴을 쓰지 않는다(`scripts/check_game_determinism.py` 회귀).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Coefficient:
    """값과 출처의 쌍. `source`가 곧 화면의 가정치 배지 여부다."""

    value: float
    source: str  # "rule" = 게임 규칙(가정치) · "observed" = 실데이터

    @property
    def assumed(self) -> bool:
        return self.source != "observed"


# --- 임대료 -----------------------------------------------------------------
# 실측 대체재가 없어 매출에 비례시킨다. 상권이 좋을수록 매출도 임대료도 높다는 관계는
# 방향만 맞고 크기는 가정이다.
#
# ⚠️ 0.18은 현실 임대료율(매출의 10~15%)보다 높다. 게임에서 **이 값이 난이도를 만든다** —
# 임대료는 상권 평균 매출 기준으로 고정되므로, 입지를 잘못 골라 실매출이 기준에 못 미치면
# 매출 대비 부담이 그대로 커진다(현실 임대차 계약의 성질과 같다).
# 0.10으로 두면 적합도 0.79짜리 나쁜 입지도 흑자가 나 "절반은 적자"가 성립하지 않았다.
RENT_RATIO = Coefficient(0.18, source="rule")  # 월임대료 ÷ 점포당 월매출
RENT_LOCATION_MIN = Coefficient(0.6, source="rule")  # 유동인구 하위 상권
RENT_LOCATION_MAX = Coefficient(1.6, source="rule")  # 유동인구 상위 상권
DEPOSIT_MONTHS = Coefficient(2.0, source="rule")  # ⚠️ 실제 관행은 10개월 안팎이다.
# 게임은 2개월로 낮춘다 — 10개월이면 초기 자본으로 어떤 규모도 창업할 수 없다.

# --- 인건비 -----------------------------------------------------------------
BASE_WAGE_MONTHLY = Coefficient(2_300_000, source="rule")  # 1인 월 인건비(최저임금 월환산 근사)

# --- 원가율 (업종 대분류) ----------------------------------------------------
# 서울 상권분석서비스 업종코드 체계: CS1=외식 10종 · CS2=서비스 21종 · CS3=소매 31종
COGS_BY_CATEGORY = {
    "CS1": Coefficient(0.40, source="rule"),  # 외식 — 식자재
    "CS2": Coefficient(0.20, source="rule"),  # 서비스 — 원가보다 인건비가 지배적
    "CS3": Coefficient(0.65, source="rule"),  # 소매 — 매입원가
}
COGS_DEFAULT = Coefficient(0.45, source="rule")

# --- 공과금 -----------------------------------------------------------------
UTILITY_SALES_RATIO = Coefficient(0.03, source="rule")
UTILITY_FIXED_MONTHLY = Coefficient(300_000, source="rule")

# --- 시설 -------------------------------------------------------------------
INTERIOR_COST_PER_POINT = Coefficient(3_000, source="rule")  # 시설점수 1점당 인테리어 비용
SEATS_PER_FACILITY_POINT = Coefficient(0.1, source="rule")  # 10점당 좌석 1석 (아이러브커피 ①)
FACILITY_SCORE_FOR_MAX_TURNOVER = Coefficient(850, source="rule")  # 원작의 "최속" 임계값
TURNOVER_MIN = Coefficient(0.4, source="rule")  # 시설 0점일 때 회전율 계수
BASE_TURNOVER_PER_SEAT = Coefficient(6.0, source="rule")  # 좌석 1석의 하루 최대 회전 수

# --- 규모 -------------------------------------------------------------------
# 상권 실데이터의 점포당 월매출은 수천만 원이라 초기 자본으로는 그 규모를 감당할 수 없다.
# "작게 시작해서 키운다"로 푼다 — 투입 자본이 규모(scale)를 정하고 매출·비용이 함께 스케일된다.
MIN_STORE_SCALE = Coefficient(0.02, source="rule")
MAX_STORE_SCALE = Coefficient(1.00, source="rule")  # 상권 평균 점포와 같은 규모

# --- 시뮬레이션 -------------------------------------------------------------
AWARENESS_TAU_DAYS = Coefficient(30.0, source="rule")  # 인지도가 붙는 시간 상수(게임일)
AWARENESS_FLOOR = Coefficient(0.15, source="rule")  # 개업 첫날에도 이만큼은 온다
DAILY_NOISE_RANGE = Coefficient(0.12, source="rule")  # ±12%
DAYS_PER_MONTH = Coefficient(30.0, source="rule")


def cogs_ratio(service_code: str) -> Coefficient:
    """업종 대분류(코드 앞 3자)로 원가율을 고른다."""
    return COGS_BY_CATEGORY.get(service_code[:3], COGS_DEFAULT)
