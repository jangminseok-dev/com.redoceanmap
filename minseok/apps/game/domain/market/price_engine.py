"""가상 주가 엔진 — 결정론 브라운 브리지 (game-harness §1-2).

가격은 **저장하지 않는다.** `price_at(params, tick)`이 정본이고, 같은 입력은 언제 물어도 같은
값이다. 누적 재귀(`p[t] = p[t-1] × …`)를 쓰지 않으므로 경과 틱과 무관하게 호출 비용이 일정하다 —
현실 10일 미접속(게임 240일 = 14,400틱) 뒤 복귀해도 첫 조회가 즉시 끝난다.

구현은 **틱 단위 단일 브라운 브리지**다. 구간 `[0, 2^16]`을 이분 분할하며 목표 틱을 향해
내려가므로 호출당 정규난수 16개(= blake2b 32회)로 끝난다. 일봉이 필요하면 `t = d × 60`에서
평가하면 된다 — 브라운 운동의 자기유사성 덕에 별도의 일봉 축이 필요 없다.
"""
from __future__ import annotations

import math

from game.domain.clock.game_epoch import SEASON_TICKS, TICKS_PER_GAME_DAY
from game.domain.market.symbol_params import SIGMA_GAME_MULTIPLIER, SymbolParams
from game.domain.rng.deterministic import normal

# 2의 거듭제곱이라야 이분 분할이 정확히 떨어진다. SEASON_TICKS(43,200)를 덮는 최소값.
_BRIDGE_SPAN = 1 << 16  # 65_536


def _midpoint(symbol: str, lo: int, hi: int, w_lo: float, w_hi: float) -> float:
    """브라운 브리지 중점.

    양 끝이 고정된 브라운 운동에서 중점의 조건부 분포는
    평균 `(w_lo + w_hi) / 2`, 분산 `(hi - lo) / 4`인 정규분포다.
    시드가 `(lo, hi)` 쌍이므로 같은 노드는 어느 경로로 내려와도 같은 값이 된다.
    """
    sigma = math.sqrt((hi - lo) / 4.0)
    return (w_lo + w_hi) / 2.0 + normal("bm-mid", f"{symbol}|{lo}|{hi}") * sigma


def _brownian(symbol: str, tick: int) -> float:
    """`[0, _BRIDGE_SPAN]` 구간 표준 브라운 운동의 tick 위치 값. W(0)=0, Var[W(t)]=t."""
    if tick <= 0:
        return 0.0
    lo, hi = 0, _BRIDGE_SPAN
    w_lo = 0.0
    w_hi = normal("bm-end", symbol) * math.sqrt(_BRIDGE_SPAN)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        w_mid = _midpoint(symbol, lo, hi, w_lo, w_hi)
        if tick == mid:
            return w_mid
        if tick < mid:
            hi, w_hi = mid, w_mid
        else:
            lo, w_lo = mid, w_mid
    return w_lo if tick == lo else w_hi


def price_at(params: SymbolParams, tick: int) -> int:
    """틱 시점 가격(원).

    금액은 **정수 원**으로 다룬다 — 부동소수를 누적하면 오차가 조용히 쌓인다.
    """
    t = max(0, min(tick, SEASON_TICKS))
    days = t / TICKS_PER_GAME_DAY
    # 틱 단위 변동성. sigma_tick × sqrt(60틱) = 일간 변동성이 되도록 나눈다.
    sigma_tick = params.sigma_daily * SIGMA_GAME_MULTIPLIER / math.sqrt(TICKS_PER_GAME_DAY)
    log_price = (
        math.log(params.base_price_krw)
        + params.mu_daily * days
        + sigma_tick * _brownian(params.symbol, t)
    )
    return max(1, round(math.exp(log_price)))


def price_series(params: SymbolParams, end_tick: int, count: int) -> list[tuple[int, int]]:
    """`end_tick`에서 끝나는 최근 `count`개 틱의 (틱, 가격) 목록. 오름차순.

    미래 틱은 만들지 않는다(§1-6) — 호출자가 `end_tick`을 현재 틱으로 넘긴다.
    """
    start = max(0, end_tick - count + 1)
    return [(t, price_at(params, t)) for t in range(start, end_tick + 1)]


def change_pct(params: SymbolParams, tick: int, lookback_ticks: int) -> float:
    """`lookback_ticks` 전 대비 등락률(%). 기준 시점이 음수면 0틱을 쓴다."""
    base = price_at(params, max(0, tick - lookback_ticks))
    if base <= 0:
        return 0.0
    return (price_at(params, tick) - base) / base * 100.0
