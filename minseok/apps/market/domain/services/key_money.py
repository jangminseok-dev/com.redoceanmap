"""권리금 기본값 — 사용자가 권리금을 말하지 않았을 때 R-ONE 서울 업종군 실측으로 채운다(순수 함수).

2026-09-17 이전엔 "권리금 0 가정"이었다. 서울 숙박·음식점업은 권리금 있는 점포가 80%(2025, 중위수 3,990만원)라
0 가정은 카페·음식점 창업의 부족 자금을 크게 과소평가했다. 반대로 소매는 32%만 권리금이 있어 중위수를
기본값으로 두면 대다수 자리를 과대평가한다(2025 도매·소매 31%) — 그래서 **업종군 절반 이상이 권리금을 낼 때만** 중위수를 가정하고,
그 밖에는 0으로 두되 비율·중위수를 가정 문구에 병기한다.
"""
from __future__ import annotations

from market.domain.services.finance_narrator import won
from market.domain.value_objects.finance_vo import KeyMoneyBenchmark, Source, Sourced

ASSUME_MEDIAN_MIN_RATIO = 50.0  # 권리금 있는 점포 비율(%)이 이 이상인 업종군만 중위수를 기본값으로

ALL = "전체"
FOOD_LODGING = "숙박 및 음식점업"
RETAIL = "도매 및 소매"
REAL_ESTATE = "부동산 및 임대업"
LEISURE = "예술,스포츠 및, 여가 관련 서비스업"
PERSONAL_SERVICE = "협회 및 단체,수리 및 기타 개인 서비스업"

# 서울시 서비스업(CS2) 코드 → 표준산업분류 대분류. 목록에 없는 CS2(학원·의원·법무·세무·독서실·여행사 등)는 '전체'.
_SERVICE_GROUPS: dict[str, str] = {
    **{code: FOOD_LODGING for code in ("CS200034", "CS200035", "CS200036")},          # 여관·게스트하우스·고시원
    "CS200033": REAL_ESTATE,                                                           # 부동산중개업
    **{code: LEISURE for code in ("CS200016", "CS200017", "CS200018", "CS200019", "CS200020",
                                  "CS200021", "CS200022", "CS200024", "CS200037", "CS200039")},  # 오락장·스포츠클럽·노래방 등
    **{code: PERSONAL_SERVICE for code in ("CS200023", "CS200025", "CS200026", "CS200027", "CS200028",
                                           "CS200029", "CS200030", "CS200031", "CS200032")},     # 수리·미용·네일·세탁 등
}


def industry_group_for(service_code: str) -> str:
    """서울시 업종 코드 → R-ONE 권리금 업종 대분류. 외식(CS1)은 숙박·음식점업, 소매(CS3)는 도매·소매."""
    if service_code.startswith("CS1"):
        return FOOD_LODGING
    if service_code.startswith("CS3"):
        return RETAIL
    return _SERVICE_GROUPS.get(service_code, ALL)


def default_key_money(bench: KeyMoneyBenchmark | None) -> Sourced:
    if bench is None or bench.key_money_ratio is None or not bench.median_krw:
        return Sourced(0, Source.ASSUMED, "권리금 자료 없음 — 0 가정")
    basis = f"R-ONE {bench.year} 서울 {bench.industry_group}"
    if bench.key_money_ratio >= ASSUME_MEDIAN_MIN_RATIO:
        return Sourced(
            bench.median_krw, Source.ASSUMED,
            f"권리금 {won(bench.median_krw)} 가정({basis} 권리금 있는 점포 중위수, 있는 비율 {bench.key_money_ratio:.0f}%)",
        )
    return Sourced(
        0, Source.ASSUMED,
        f"권리금 0 가정({basis}은 권리금 있는 점포가 {bench.key_money_ratio:.0f}%, 있으면 중위수 {won(bench.median_krw)})",
    )
