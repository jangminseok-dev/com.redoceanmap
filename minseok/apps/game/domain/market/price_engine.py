"""가상 주가 엔진 — 결정론 브라운 브리지 (game-harness §1-2).

가격은 **저장하지 않는다.** `price_at(params, tick)`이 정본이고, 같은 입력은 언제 물어도 같은
값이다. 누적 재귀(`p[t] = p[t-1] × …`)를 쓰지 않으므로 경과 틱과 무관하게 호출 비용이 일정하다 —
현실 10일 미접속(게임 240일 = 14,400틱) 뒤 복귀해도 첫 조회가 즉시 끝난다.

구현은 **틱 단위 단일 브라운 브리지**다. 구간 `[0, 2^16]`을 이분 분할하며 목표 틱을 향해
내려가므로 호출당 정규난수 16개(= blake2b 32회)로 끝난다. 일봉이 필요하면 `t = d × 60`에서
평가하면 된다 — 브라운 운동의 자기유사성 덕에 별도의 일봉 축이 필요 없다.

여기에 **이벤트 충격**(`market_events.impact`)이 더해진다. 창(게임 3일) 밖 이벤트는 계산에서
빠지므로 이 항도 경과 시간과 무관하게 비용이 일정하다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from game.domain.clock.game_epoch import SEASON_TICKS, TICKS_PER_GAME_DAY
from game.domain.market import market_events
from game.domain.market.symbol_params import (
    MEME_SIGMA_MULTIPLIER,
    SIGMA_GAME_MULTIPLIER,
    SYMBOLS,
    SymbolParams,
)
from game.domain.rng.deterministic import normal

# 2의 거듭제곱이라야 이분 분할이 정확히 떨어진다. SEASON_TICKS(43,200)를 덮는 최소값.
_BRIDGE_SPAN = 1 << 16  # 65_536

# 가격 밴드 — 기준가 대비 로그비를 `band × tanh(x / band)`로 눌러 시즌 내내 유의미한 범위에
# 머물게 한다. **클램프가 아니라 tanh다**: 작은 변동(±30%)에서는 사실상 항등이라 일상적인
# 곡선을 왜곡하지 않고, 꼬리에서만 부드럽게 눌려 밴드를 넘지 않는다(정지화면이 생기지 않는다).
#
# 왜 필요한가: 시즌이 720 게임일이라 σ가 커지면 누적 변동이 폭발한다. 실측(밴드 없음)에서
# 밈 종목이 시즌 중 기준가의 **1,461배**까지 갔다 — 그 종목을 안 산 유저는 무엇을 해도
# 따라잡을 수 없어 나머지 35종목이 의미를 잃는다. 반대쪽 꼬리는 -97%로 상장폐지가 된다.
PRICE_BAND_LOG = 2.3       # 일반 종목 — 약 ×10 / ÷10
PRICE_BAND_LOG_MEME = 3.0  # 밈 종목 — 약 ×20 / ÷20. 더 크게 열어두되 무한하지 않다


def _midpoint(symbol: str, lo: int, hi: int, w_lo: float, w_hi: float) -> float:
    """브라운 브리지 중점.

    양 끝이 고정된 브라운 운동에서 중점의 조건부 분포는
    평균 `(w_lo + w_hi) / 2`, 분산 `(hi - lo) / 4`인 정규분포다.
    시드가 `(lo, hi)` 쌍이므로 같은 노드는 어느 경로로 내려와도 같은 값이 된다.
    """
    sigma = math.sqrt((hi - lo) / 4.0)
    return (w_lo + w_hi) / 2.0 + normal("bm-mid", f"{symbol}|{lo}|{hi}") * sigma


def _brownian(symbol: str, tick: int, nodes: dict[tuple[int, int], float] | None = None) -> float:
    """`[0, _BRIDGE_SPAN]` 구간 표준 브라운 운동의 tick 위치 값. W(0)=0, Var[W(t)]=t.

    `nodes`는 한 번의 조회 묶음(시리즈·일봉) 안에서만 쓰는 중점 캐시다. 트리는 위에서
    아래로 유일하게 결정되므로 `(lo, hi)` 노드의 값은 어느 틱에서 내려와도 같다 —
    **캐시가 값을 바꾸지 않는다.** 연속 틱은 상위 노드를 거의 전부 공유하므로,
    240틱 시리즈에서 정규난수 3,840회가 500회 수준으로 줄어든다.
    """
    if tick <= 0:
        return 0.0
    lo, hi = 0, _BRIDGE_SPAN
    w_lo = 0.0
    if nodes is None:
        w_hi = normal("bm-end", symbol) * math.sqrt(_BRIDGE_SPAN)
    else:
        end_key = (_BRIDGE_SPAN, _BRIDGE_SPAN)
        w_hi = nodes.get(end_key)
        if w_hi is None:
            w_hi = normal("bm-end", symbol) * math.sqrt(_BRIDGE_SPAN)
            nodes[end_key] = w_hi
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if nodes is None:
            w_mid = _midpoint(symbol, lo, hi, w_lo, w_hi)
        else:
            w_mid = nodes.get((lo, hi))
            if w_mid is None:
                w_mid = _midpoint(symbol, lo, hi, w_lo, w_hi)
                nodes[(lo, hi)] = w_mid
        if tick == mid:
            return w_mid
        if tick < mid:
            hi, w_hi = mid, w_mid
        else:
            lo, w_lo = mid, w_mid
    return w_lo if tick == lo else w_hi


def price_at(
    params: SymbolParams,
    tick: int,
    nodes: dict[tuple[int, int], float] | None = None,
    extra_events: tuple[market_events.MarketEvent, ...] = (),
) -> int:
    """틱 시점 가격(원).

    금액은 **정수 원**으로 다룬다 — 부동소수를 누적하면 오차가 조용히 쌓인다.
    `nodes`는 연속 틱을 여러 번 물을 때 쓰는 브리지 캐시다(값은 바뀌지 않는다).
    `extra_events`는 저장소에서 읽어 넘긴 관리자 개입이다 — 비어 있으면 순수 결정론이다.
    """
    t = max(0, min(tick, SEASON_TICKS))
    days = t / TICKS_PER_GAME_DAY
    # 틱 단위 변동성. sigma_tick × sqrt(60틱) = 일간 변동성이 되도록 나눈다.
    # 밈 종목은 캘리브레이션 클립 위로 한 번 더 곱한다 — 실데이터 σ(전 기간 평균)로는
    # "평소엔 잠잠하다 한 번에 몇 배"가 재현되지 않는다.
    sigma_daily = params.sigma_daily * (MEME_SIGMA_MULTIPLIER if params.meme else 1.0)
    sigma_tick = sigma_daily * SIGMA_GAME_MULTIPLIER / math.sqrt(TICKS_PER_GAME_DAY)
    log_ratio = (
        params.mu_daily * days
        + sigma_tick * _brownian(params.symbol, t, nodes)
        # 호재·악재 — 창 밖 이벤트는 계산에서 빠진다. 관리자 개입도 같은 항으로 들어간다
        + market_events.impact(params, t, extra_events)
    )
    band = PRICE_BAND_LOG_MEME if params.meme else PRICE_BAND_LOG
    log_price = math.log(params.base_price_krw) + band * math.tanh(log_ratio / band)
    return max(1, round(math.exp(log_price)))


def price_series(
    params: SymbolParams,
    end_tick: int,
    count: int,
    extra_events: tuple[market_events.MarketEvent, ...] = (),
) -> list[tuple[int, int]]:
    """`end_tick`에서 끝나는 최근 `count`개 틱의 (틱, 가격) 목록. 오름차순.

    미래 틱은 만들지 않는다(§1-6) — 호출자가 `end_tick`을 현재 틱으로 넘긴다.
    """
    start = max(0, end_tick - count + 1)
    nodes: dict[tuple[int, int], float] = {}
    return [(t, price_at(params, t, nodes, extra_events)) for t in range(start, end_tick + 1)]


INDEX_BASE_POINT = 1_000  # 시즌 시작 시점의 지수값


def index_at(
    tick: int, extra_events: tuple[market_events.MarketEvent, ...] = ()
) -> int:
    """시장 지수 `GXI` — 전 종목 상대가격의 **기하평균** × 1000.

    금액 가중이 아니라 상대가격(현재가 ÷ 시작가)인 이유: 기준가가 18,900원부터 154,000원까지
    8배 차이라 금액으로 묶으면 비싼 종목 하나가 지수를 지배한다.

    **산술평균이 아니라 기하평균인 것이 핵심이다.** 가격이 로그정규라 산술평균은
    `E[P/P₀] = exp(σ²t/2) > 1`이라는 구조적 상승 편향을 갖는다 — μ를 0으로 중심화해도
    지수만 계속 오르고, 그러면 선물 롱이 언제나 유리한 한쪽짜리 게임이 된다(실측: 산술은
    시즌 중 1000→3142, 기하는 1000→1851이며 후자는 이 시즌의 실현 경로일 뿐 편향이 아니다).
    로그 공간에서 평균하면 μ 중심화가 그대로 지수에 전달된다.

    새 σ 캘리브레이션이 필요 없다 — 종목 파라미터에서 유도되므로 에포크를 따로 건드리지 않는다.
    비용은 종목 수만큼(36종목 실측 1.3ms)이라 **틱 단위 순회에는 쓰지 않는다**(선물이 청산
    스캔을 두지 않는 이유이기도 하다).
    """
    log_total = sum(
        math.log(price_at(s, tick, None, extra_events) / s.base_price_krw) for s in SYMBOLS
    )
    return max(1, round(INDEX_BASE_POINT * math.exp(log_total / len(SYMBOLS))))


@dataclass(frozen=True)
class Candle:
    """게임 1일(60틱) OHLC 봉 하나. `game_day`는 에포크 기준 일차다."""

    game_day: int
    open_krw: int
    high_krw: int
    low_krw: int
    close_krw: int


def daily_candles(
    params: SymbolParams,
    end_tick: int,
    days: int,
    extra_events: tuple[market_events.MarketEvent, ...] = (),
) -> tuple[Candle, ...]:
    """`end_tick`이 속한 날에서 끝나는 최근 `days`개 일봉. 오름차순.

    브라운 운동의 자기유사성 덕에 별도의 일봉 축이 필요 없다 — 하루치 60틱을 그대로
    훑어 극값을 잡는다. **하루당 60회 평가라 전 종목에 돌리지 않는다** — 호출자가 선택 종목
    하나만 넘긴다.

    마지막 봉은 **진행 중**일 수 있다 — 미래 틱은 만들지 않으므로(§1-6) 현재 틱까지만 훑는다.
    """
    end = max(0, min(end_tick, SEASON_TICKS))
    last_day = end // TICKS_PER_GAME_DAY
    first_day = max(0, last_day - days + 1)

    nodes: dict[tuple[int, int], float] = {}
    out = []
    for day in range(first_day, last_day + 1):
        start_tick = day * TICKS_PER_GAME_DAY
        stop_tick = min(start_tick + TICKS_PER_GAME_DAY - 1, end)
        prices = [
            price_at(params, t, nodes, extra_events)
            for t in range(start_tick, stop_tick + 1)
        ]
        out.append(
            Candle(
                game_day=day,
                open_krw=prices[0],
                high_krw=max(prices),
                low_krw=min(prices),
                close_krw=prices[-1],
            )
        )
    return tuple(out)


def change_pct(
    params: SymbolParams,
    tick: int,
    lookback_ticks: int,
    extra_events: tuple[market_events.MarketEvent, ...] = (),
) -> float:
    """`lookback_ticks` 전 대비 등락률(%). 기준 시점이 음수면 0틱을 쓴다."""
    base = price_at(params, max(0, tick - lookback_ticks), None, extra_events)
    if base <= 0:
        return 0.0
    return (price_at(params, tick, None, extra_events) - base) / base * 100.0
