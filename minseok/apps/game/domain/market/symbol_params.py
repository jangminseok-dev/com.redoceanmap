"""게임 종목 파라미터 — 캘리브레이션 산출물 (game-harness §3-2).

`scripts/calibrate_game_symbols.py`가 stock의 `price_bars`(1d)에서 종목별 σ·μ를 뽑아
**이 파일을 덮어쓴다.** 런타임에 DB를 읽지 않는다 — 봉이 하루 갱신될 때마다 σ가 미세하게
바뀌고, 그러면 과거 주가 전 구간이 소급 변조되기 때문이다(§1-A · §1-4 위반).

**종목명은 가상이다**(§2). 실 티커 매핑은 캘리브레이션 스크립트 안에서 익명화되고 이 파일에
남지 않는다 — 가상 주가에 실명을 붙이면 실시세로 오인되고, 서버가 만든 가짜 악재가 실재
기업에 대한 허위정보처럼 읽힌다. 업종만 실제에서 가져와 섹터 이벤트의 서사를 살린다.

⚠️ **아래 값은 캘리브레이션 미실행 상태의 잠정값이다(2026-07-31).**
   주식 실데이터가 백엔드 PC에만 있어 이 맥에서는 산출할 수 없다.
   실행 후 `CALIBRATED_AT`를 채우고 `GAME_EPOCH_ID`를 올린다(§1-4).
"""
from __future__ import annotations

from dataclasses import dataclass

# 캘리브레이션 실행 시각(ISO). None이면 잠정값이라는 뜻이며 API 응답의 basis에 노출된다.
CALIBRATED_AT: str | None = None

# 게임 체감용 변동성 배수 — 현실 1시간(게임 1일)만 봐도 하루치 변동이 지나가야 한다.
SIGMA_GAME_MULTIPLIER = 1.5

# 캘리브레이션 클리핑 범위(스크립트와 이 파일이 같은 값을 써야 한다)
SIGMA_CLIP_MIN = 0.008   # 이상치 저변동 종목이 정지화면처럼 보이지 않게
SIGMA_CLIP_MAX = 0.060   # 이상치 고변동 종목이 게임을 지배하지 않게
MU_CLIP = 0.0005


@dataclass(frozen=True)
class SymbolParams:
    """종목 하나의 가격 생성 파라미터."""

    symbol: str
    name: str
    sector: str
    base_price_krw: int
    sigma_daily: float   # 일간 로그수익 표준편차 (SIGMA_CLIP 범위로 클리핑됨)
    mu_daily: float      # 일간 로그수익 드리프트 (전 종목 합이 0이 되도록 중심화됨)


# ⚠️ mu_daily는 **전 종목 합이 0**이다. 실드리프트를 그대로 쓰면 우상향 종목을 사서 방치하는
#    것이 유일한 최적 전략이 되어 게임이 성립하지 않는다(game-strategy §3-1).
SYMBOLS: tuple[SymbolParams, ...] = (
    SymbolParams("GX01", "세빛반도체", "반도체", 71_000, 0.032, +0.00030),
    SymbolParams("GX02", "무진중공업", "조선·기계", 28_500, 0.028, +0.00020),
    SymbolParams("GX03", "예린바이오", "제약·바이오", 154_000, 0.045, +0.00010),
    SymbolParams("GX04", "하늬모빌리티", "전기차", 92_000, 0.048, +0.00040),
    SymbolParams("GX05", "온누리식품", "식음료", 41_200, 0.013, -0.00020),
    SymbolParams("GX06", "두무개금융", "금융", 18_900, 0.015, -0.00010),
    SymbolParams("GX07", "노을텔레콤", "통신", 33_400, 0.011, -0.00030),
    SymbolParams("GX08", "미르에너지", "정유·에너지", 57_800, 0.022, 0.00000),
    SymbolParams("GX09", "나래유통", "유통", 24_600, 0.018, -0.00015),
    SymbolParams("GX10", "가온소프트", "소프트웨어", 118_000, 0.026, +0.00025),
    SymbolParams("GX11", "벼리소재", "화학·소재", 46_300, 0.024, -0.00025),
    SymbolParams("GX12", "너울항공", "항공·운송", 21_700, 0.038, -0.00025),
)

_BY_SYMBOL = {p.symbol: p for p in SYMBOLS}


def find(symbol: str) -> SymbolParams | None:
    """종목 코드로 파라미터 조회. 없으면 None."""
    return _BY_SYMBOL.get(symbol)
