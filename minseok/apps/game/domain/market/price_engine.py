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
from functools import lru_cache

from game.domain.clock.game_epoch import SEASON_TICKS, TICKS_PER_GAME_DAY
from game.domain.market import fundamentals, market_events
from game.domain.market.symbol_params import (
    MEME_SIGMA_MULTIPLIER,
    SIGMA_GAME_MULTIPLIER,
    SYMBOLS,
    SymbolParams,
)
from game.domain.rng.deterministic import normal, uniform

# 2의 거듭제곱이라야 이분 분할이 정확히 떨어진다. SEASON_TICKS(43,200)를 덮는 최소값.
_BRIDGE_SPAN = 1 << 16  # 65_536

# 가격 밴드 — 기준가 대비 로그비를 `band × tanh(x / band)`로 눌러 시즌 내내 유의미한 범위에
# 머물게 한다. **클램프가 아니라 tanh다**: 작은 변동(±30%)에서는 사실상 항등이라 일상적인
# 곡선을 왜곡하지 않고, 꼬리에서만 부드럽게 눌려 밴드를 넘지 않는다(정지화면이 생기지 않는다).
#
# 왜 필요한가: 시즌이 720 게임일이라 σ가 커지면 누적 변동이 폭발한다. 실측(밴드 없음)에서
# 밈 종목이 시즌 중 기준가의 **1,461배**까지 갔다 — 그 종목을 안 산 유저는 무엇을 해도
# 따라잡을 수 없어 나머지 35종목이 의미를 잃는다. 반대쪽 꼬리는 -97%로 상장폐지가 된다.
# 일일 가격제한폭 — 한국거래소와 같은 ±30%. 시즌 누적 밴드(아래)와 축이 다르다:
# 이쪽은 **그날 시가 대비** 하루 안의 변동을 막는다. 폭락·폭등이 하루에 끝나지 않고
# 며칠에 걸쳐 이어지게 만드는 장치이고, 실제 시장의 가장 눈에 띄는 제도이기도 하다.
DAILY_LIMIT_PCT = 0.30

# 호가 단위(tick size) — 한국거래소 규칙 그대로. 가격대가 높을수록 단위가 커진다.
# 이게 없으면 3,200원짜리 종목이 1원 단위로 움직여 실제 시장과 다르게 보인다
# (실측에서 저가 밈 종목이 "계단형"으로 걸렸는데, 진짜 원인은 호가 단위가 없어서였다).
_TICK_SIZE_TABLE = (
    (2_000, 1),
    (5_000, 5),
    (20_000, 10),
    (50_000, 50),
    (200_000, 100),
    (500_000, 500),
)
_TICK_SIZE_TOP = 1_000


def tick_size(price_krw: int) -> int:
    """그 가격대의 호가 단위(원). 주문·호가창·표시가 전부 이 격자 위에 선다."""
    for ceiling, size in _TICK_SIZE_TABLE:
        if price_krw < ceiling:
            return size
    return _TICK_SIZE_TOP


def round_to_tick(price_krw: int) -> int:
    """호가 단위로 맞춘다. 1원 미만으로는 내려가지 않는다."""
    size = tick_size(price_krw)
    return max(size, round(price_krw / size) * size)

PRICE_BAND_LOG = 1.8       # 일반 종목 — 약 ×6 / ÷6
PRICE_BAND_LOG_MEME = 2.5  # 밈 종목 — 약 ×12 / ÷12. 더 크게 열어두되 무한하지 않다

# --- 확률적 변동성 (실시장 대조 후 도입, 2026-08-03) ---------------------------
# σ가 상수이던 모델은 실시장의 가장 뚜렷한 성질 둘을 재현하지 못했다.
# 실측(실데이터 68종목 vs 게임 36종목):
#   |수익률| 자기상관(변동성 클러스터링)  실 +0.117  vs  게임 +0.012
#   레버리지 효과(하락 뒤 변동성↑)      실 -0.008  vs  게임 +0.009 (부호가 반대)
#
# 해법은 **시간 변경(time change)**이다. 가격을 σ(t)의 적분으로 만들지 않고,
# 브라운 운동을 "활동 시간" τ에서 평가한다 — logP = μt + σ̄·W(τ(t)).
# 활동이 활발한 날은 τ가 빨리 흘러 같은 σ̄로도 크게 움직인다.
#
# τ는 일별 활동계수의 누적합이고, 활동계수는
#   ① 로그공간 AR(1) — 어제 활발했으면 오늘도 활발하다(클러스터링)
#   ② 전일 하락폭에 비례한 가산 — 떨어진 다음 날 더 흔들린다(레버리지 효과)
# 로 만든다. ②가 전일 수익률을 보므로 **일별로는 순차 계산**이 된다.
VOL_AR_PHI = 0.90          # 로그 변동성의 하루 지속성. 1에 가까울수록 클러스터가 길다
VOL_OF_VOL = 0.35          # 로그 변동성의 하루 충격 크기
LEVERAGE_K = 2.2           # 전일 하락 1% → 다음 날 활동 +2.2%
MAX_DAILY_ACTIVITY = 6.0   # 활동계수 상한 — 폭주로 하루에 시즌이 끝나지 않게


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


_SEASON_DAYS = SEASON_TICKS // TICKS_PER_GAME_DAY
# 로그 변동성 AR(1)의 정상분산. exp(logv - var/2)로 평균을 1에 맞춘다 —
# 맞추지 않으면 활동시간이 하루 1.4배씩 빨라져 시즌 전체 변동성이 통째로 커진다.
_VOL_STATIONARY_VAR = VOL_OF_VOL**2 / (1.0 - VOL_AR_PHI**2)


@lru_cache(maxsize=128)
def _activity_time(symbol: str, sigma_tick: float, mu_daily: float) -> tuple[float, ...]:
    """일별 **누적 활동시간** τ. `τ[d]`는 d일차가 끝난 시점의 값이고 길이는 시즌일+1이다.

    왜 순차 계산인가: 레버리지 효과가 **전일 수익률**을 보기 때문이다. 오늘의 활동을 정하려면
    어제 얼마나 떨어졌는지 알아야 하고, 그러려면 어제 가격이 필요하다. 되먹임이 있는 모델은
    원래 이 구조다(GARCH도 같다).

    **경과 시간과 무관한 비용이라는 약속은 지킨다**(§1-2). 시즌 길이가 고정(720일)이라 배열이
    유한하고 종목당 한 번만 만들어 캐시한다 — 현실 10일 미접속 뒤 복귀해도 이 배열은 이미
    있거나 한 번만 만들면 된다. 캐시는 순수 함수의 재계산 제거일 뿐 값을 바꾸지 않는다.

    σ·μ를 인자로 받는 것은 캐시 키를 종목 파라미터에 묶기 위해서다 — 캘리브레이션이 바뀌면
    키가 달라져 옛 배열이 재사용되지 않는다.
    """
    tau = [0.0]
    log_vol = 0.0        # 로그 변동성 AR(1) 상태
    prev_log = 0.0       # 전일 종가의 로그비
    prev_return = 0.0    # 전일 로그수익률 — 레버리지 효과의 입력
    nodes: dict[tuple[int, int], float] = {}

    for day in range(1, _SEASON_DAYS + 1):
        shock = uniform("vol-state", f"{symbol}|{day}") * 2 - 1
        log_vol = VOL_AR_PHI * log_vol + VOL_OF_VOL * shock
        # **하락분만** 활동을 키운다. 상승도 키우면 그냥 변동성이 커질 뿐이고,
        # "떨어질 때 더 흔들린다"는 비대칭이 레버리지 효과의 정의다.
        leverage = 1.0 + LEVERAGE_K * max(0.0, -prev_return)
        activity = math.exp(log_vol - _VOL_STATIONARY_VAR / 2.0) * leverage
        tau.append(tau[-1] + min(MAX_DAILY_ACTIVITY, activity))

        log_price = mu_daily * day + sigma_tick * _brownian(
            symbol, _bridge_tick(tau[-1]), nodes
        )
        prev_return = log_price - prev_log
        prev_log = log_price
    return tuple(tau)


def _bridge_tick(tau_days: float) -> int:
    """활동시간(일) → 브리지 좌표(틱). 브리지 구간을 넘지 않게 자른다."""
    return min(_BRIDGE_SPAN, max(0, round(tau_days * TICKS_PER_GAME_DAY)))


def _tau_at(params: SymbolParams, tick: int, sigma_tick: float) -> float:
    """틱 시점의 활동시간. 하루 안에서는 그날의 활동 속도로 선형 보간한다."""
    series = _activity_time(params.symbol, sigma_tick, params.mu_daily)
    day = min(tick // TICKS_PER_GAME_DAY, len(series) - 1)
    within = (tick % TICKS_PER_GAME_DAY) / TICKS_PER_GAME_DAY
    start = series[day]
    end = series[min(day + 1, len(series) - 1)]
    return start + (end - start) * within


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
    # **시간 변경**: 실제 틱이 아니라 활동시간 τ에서 브라운 운동을 평가한다.
    # 활발한 날은 τ가 빨리 흘러 같은 σ̄로도 크게 움직인다 — 변동성 클러스터링과
    # 레버리지 효과가 여기서 나온다.
    log_ratio = (
        params.mu_daily * days
        + sigma_tick * _brownian(params.symbol, _bridge_tick(_tau_at(params, t, sigma_tick)), nodes)
        # 호재·악재 — 창 밖 이벤트는 계산에서 빠진다. 관리자 개입도 같은 항으로 들어간다
        + market_events.impact(params, t, extra_events + _earnings(params))
    )
    band = PRICE_BAND_LOG_MEME if params.meme else PRICE_BAND_LOG
    log_price = math.log(params.base_price_krw) + band * math.tanh(log_ratio / band)
    raw = max(1, round(math.exp(log_price)))
    limited = _apply_daily_limit(params, t, raw, nodes, extra_events)
    return round_to_tick(limited)


def _apply_daily_limit(
    params: SymbolParams,
    tick: int,
    raw_price: int,
    nodes: dict[tuple[int, int], float] | None,
    extra_events: tuple[market_events.MarketEvent, ...],
) -> int:
    """그날 시가 대비 ±`DAILY_LIMIT_PCT`로 자른다(상한가·하한가).

    시가는 그날 첫 틱의 **제한 없는** 가격이다 — 시가에도 제한을 걸면 전일 종가를 알아야 하고
    그러면 하루씩 거슬러 올라가는 재귀가 된다. 게임에는 동시호가가 없으므로 이 단순화가 맞다.

    상한가에 붙으면 그날은 더 오르지 않는다. 실제 시장에서 폭등이 하루에 끝나지 않고
    며칠에 걸쳐 이어지는 이유이고, 유저에게는 "오늘은 여기까지"라는 리듬을 만든다.
    """
    day_start = (tick // TICKS_PER_GAME_DAY) * TICKS_PER_GAME_DAY
    if tick == day_start:
        return raw_price
    # 하루 60틱이 같은 시가를 60번 다시 계산하면 시리즈 조회가 두 배로 느려진다.
    # 순수 함수라 캐시가 값을 바꾸지 않는다(개입도 키에 들어간다).
    open_price = _day_open(params, day_start, extra_events)
    ceiling = round(open_price * (1.0 + DAILY_LIMIT_PCT))
    floor = round(open_price * (1.0 - DAILY_LIMIT_PCT))
    return max(1, min(max(raw_price, floor), ceiling))


@lru_cache(maxsize=4096)
def _day_open(
    params: SymbolParams,
    day_start_tick: int,
    extra_events: tuple[market_events.MarketEvent, ...],
) -> int:
    """그날 시가(제한 적용 전). 상하한가 판정의 기준선이다."""
    return _unlimited_price(params, day_start_tick, None, extra_events)


@lru_cache(maxsize=128)
def _earnings(params: SymbolParams) -> tuple[market_events.MarketEvent, ...]:
    """이 종목의 어닝 이벤트. **가격 경로 어디서든 자동으로 포함된다** —
    호출자가 넘기게 두면 한 곳이라도 빠졌을 때 화면 가격과 체결가가 갈라진다."""
    return fundamentals.earnings_events(params)


def _unlimited_price(
    params: SymbolParams,
    tick: int,
    nodes: dict[tuple[int, int], float] | None,
    extra_events: tuple[market_events.MarketEvent, ...],
) -> int:
    """제한을 적용하기 **전**의 가격. 시가를 구할 때만 쓴다(재귀를 끊는 지점)."""
    t = max(0, min(tick, SEASON_TICKS))
    sigma_daily = params.sigma_daily * (MEME_SIGMA_MULTIPLIER if params.meme else 1.0)
    sigma_tick = sigma_daily * SIGMA_GAME_MULTIPLIER / math.sqrt(TICKS_PER_GAME_DAY)
    log_ratio = (
        params.mu_daily * (t / TICKS_PER_GAME_DAY)
        + sigma_tick * _brownian(params.symbol, _bridge_tick(_tau_at(params, t, sigma_tick)), nodes)
        + market_events.impact(params, t, extra_events + _earnings(params))
    )
    band = PRICE_BAND_LOG_MEME if params.meme else PRICE_BAND_LOG
    return max(1, round(math.exp(math.log(params.base_price_krw) + band * math.tanh(log_ratio / band))))


def limit_state(params: SymbolParams, tick: int) -> str:
    """지금 상한가·하한가에 붙어 있는가. `upper` | `lower` | `none`.

    화면이 "상한가"를 표시하고 매매 경로가 그 방향 주문을 막는 근거다.
    """
    day_start = (tick // TICKS_PER_GAME_DAY) * TICKS_PER_GAME_DAY
    if tick == day_start:
        return "none"
    open_price = _day_open(params, day_start, ())
    raw = _unlimited_price(params, tick, None, ())
    if raw >= round(open_price * (1.0 + DAILY_LIMIT_PCT)):
        return "upper"
    if raw <= round(open_price * (1.0 - DAILY_LIMIT_PCT)):
        return "lower"
    return "none"


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


# --- 거래량 -------------------------------------------------------------------
# 게임에는 호가·체결 개념이 없어 거래량이 **존재하지 않는다.** 차트가 요구하므로 규칙으로
# 만든다(`simulated_*` 접두사로 가정치임을 표시, harness §5-1).
#
# 설계: 하루 거래대금을 기준으로 잡고 주가로 나눠 주수를 얻는다 — 기준가가 18,900원인
# 종목과 214,000원인 종목의 거래량이 같으면 어색하다. 여기에 **그날 변동폭에 비례하는
# 급증**과 결정론 잡음을 곱한다. "뉴스가 뜬 날 거래량이 터진다"가 눈으로 보이게 하려는 것이다.
BASE_TURNOVER_KRW = 3_000_000_000  # 하루 기준 거래대금(가정치)
# 2.5 → 1.4 (2026-08-03): |수익률|-거래량 상관이 0.855로 실시장(0.547)보다 훨씬 결정적이었다.
# 거래량을 수익률에서만 만들면 "뉴스 없는 대량 거래"나 "조용한 급등"이 생기지 않는다.
VOLUME_SURGE_K = 1.4               # 변동폭 1σ당 거래량 배수 증가분
MEME_VOLUME_MULTIPLIER = 3.0       # 밈 종목은 평소에도 훨씬 많이 돈다
VOLUME_NOISE_RANGE = 0.70          # ±70% 결정론 잡음 — 가격과 무관한 수급을 만든다


def daily_volume(params: SymbolParams, game_day: int, day_return: float) -> int:
    """게임 1일 거래량(주). 같은 (종목, 날)이면 언제 물어도 같은 값이다.

    `day_return`은 그날의 시가 대비 종가 수익률이다 — 호출자가 봉에서 넘긴다(가격을 다시
    계산하지 않게).
    """
    sigma = params.sigma_daily * (MEME_SIGMA_MULTIPLIER if params.meme else 1.0)
    sigma = max(sigma * SIGMA_GAME_MULTIPLIER, 1e-6)
    surge = 1.0 + VOLUME_SURGE_K * min(4.0, abs(day_return) / sigma)
    noise = 1.0 + (uniform("volume", f"{params.symbol}|{game_day}") * 2 - 1) * VOLUME_NOISE_RANGE
    turnover = BASE_TURNOVER_KRW * surge * noise
    if params.meme:
        turnover *= MEME_VOLUME_MULTIPLIER
    return max(1, round(turnover / max(1, params.base_price_krw)))


@dataclass(frozen=True)
class Candle:
    """게임 1일(60틱) OHLC 봉 하나. `game_day`는 에포크 기준 일차다."""

    game_day: int
    open_krw: int
    high_krw: int
    low_krw: int
    close_krw: int
    simulated_volume: int  # 게임 규칙 산출값 — 실제 체결이 아니다


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
        day_return = (prices[-1] - prices[0]) / prices[0] if prices[0] else 0.0
        out.append(
            Candle(
                game_day=day,
                open_krw=prices[0],
                high_krw=max(prices),
                low_krw=min(prices),
                close_krw=prices[-1],
                simulated_volume=daily_volume(params, day, day_return),
            )
        )
    return tuple(out)


def daily_closes(
    params: SymbolParams,
    end_tick: int,
    days: int,
    extra_events: tuple[market_events.MarketEvent, ...] = (),
) -> list[int]:
    """최근 `days` 게임일의 **종가만**. 오름차순.

    이동평균·RSI 전용 경로다. 봉은 하루에 60회 평가지만 종가는 1회라 25배 싸다
    (실측 240일: 봉 148ms · 종가 5.7ms). 120일선을 그리려면 화면 밖으로 120일을 더 봐야
    하는데, 그 워밍업을 봉으로 하면 응답 예산을 넘긴다.

    마지막 날은 진행 중일 수 있다 — 현재 틱까지만 본다(§1-6).
    """
    end = max(0, min(end_tick, SEASON_TICKS))
    last_day = end // TICKS_PER_GAME_DAY
    first_day = max(0, last_day - days + 1)
    nodes: dict[tuple[int, int], float] = {}
    return [
        price_at(
            params,
            min(day * TICKS_PER_GAME_DAY + TICKS_PER_GAME_DAY - 1, end),
            nodes,
            extra_events,
        )
        for day in range(first_day, last_day + 1)
    ]


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
