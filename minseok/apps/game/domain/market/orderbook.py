"""호가창·체결·거래정지 — 시장 미시구조 (실시장 대조 후 도입, 2026-08-03).

지금까지 매매는 **요청 도착 틱의 가격에 즉시 전량 체결**됐다. 실제 시장에는 호가가 있고,
큰 주문은 호가를 걷어올리며 체결되므로 평균 체결가가 현재가보다 불리하다. 그 차이가
유동성이고, 유동성이 없으면 "10억을 한 번에 사도 현재가에 다 산다"는 비현실이 남는다.

**호가창도 시각의 함수다**(harness §1-A). 주문장을 저장하지 않고 `f(종목, 틱)`으로 만든다 —
게임에 다른 참가자의 실제 주문이 없으므로 잔량은 유동성 모형이 만든 값이다(`assumed_*`).

**체결 지연을 틱 단위로 두지 않았다.** 틱이 현실 1분이라 "1분 뒤 체결"은 게임 조작감을
망가뜨린다. 실제 시장에서 시장가 주문이 치르는 비용의 본체는 지연이 아니라 **슬리피지**이고,
그쪽을 구현하는 것이 같은 현상을 더 정직하게 옮긴다.
"""
from __future__ import annotations

from dataclasses import dataclass

from game.domain.clock.game_epoch import TICKS_PER_GAME_DAY
from game.domain.market.symbol_params import SymbolParams
from game.domain.rng.deterministic import uniform

# 화면에 보여줄 호가 단계 수(매도·매수 각각). 국내 증권 앱의 기본이 10단계다.
BOOK_DEPTH = 10

# 최우선 호가의 기준 잔량 — 하루 거래량의 몇 %가 1호가에 걸려 있는가.
TOP_LEVEL_SHARE = 0.004
# 호가가 멀어질수록 잔량이 는다(실제 호가창의 모양). 단계당 배수.
DEPTH_GROWTH = 1.25
# 잔량 결정론 잡음
BOOK_NOISE = 0.5

# 밈 종목은 호가가 얇다 — 같은 금액을 사도 더 많이 밀린다.
MEME_LIQUIDITY = 0.45

# --- 변동성 완화 장치(VI) ------------------------------------------------------
# 한국거래소의 정적 VI를 옮겼다. 기준가(그날 시가) 대비 이만큼 벌어지면 매매가 잠시 멈춘다.
VI_TRIGGER_PCT = 0.10
VI_HALT_TICKS = 2  # 발동 후 잠기는 틱 수(현실 2분)


@dataclass(frozen=True)
class Quote:
    price_krw: int
    assumed_quantity: int  # 게임 규칙 산출 잔량 — 실제 주문이 아니다


@dataclass(frozen=True)
class OrderBook:
    bids: tuple[Quote, ...]  # 매수 호가, 높은 가격부터
    asks: tuple[Quote, ...]  # 매도 호가, 낮은 가격부터
    spread_krw: int


@dataclass(frozen=True)
class Fill:
    """시장가 주문의 체결 결과."""

    filled_quantity: int
    avg_price_krw: int
    slippage_pct: float  # 현재가 대비 불리해진 정도(양수 = 손해)
    exhausted: bool      # 호가를 다 먹고도 수량이 남았는가


def _liquidity(params: SymbolParams, daily_volume: int) -> float:
    base = daily_volume * TOP_LEVEL_SHARE
    return base * (MEME_LIQUIDITY if params.meme else 1.0)


def build(
    params: SymbolParams, price_krw: int, tick: int, daily_volume: int, tick_size: int
) -> OrderBook:
    """`tick` 시점의 호가창. 같은 (종목, 틱)이면 언제 물어도 같다.

    최우선 매도호가는 현재가 위 1틱, 최우선 매수호가는 아래 1틱이다 — 게임에 실제 체결
    상대가 없으므로 현재가를 스프레드의 중앙으로 둔다.
    """
    top = max(1.0, _liquidity(params, daily_volume))
    bids, asks = [], []
    for level in range(BOOK_DEPTH):
        grow = DEPTH_GROWTH**level
        for side, out in (("b", bids), ("a", asks)):
            noise = 1.0 + (uniform("book", f"{params.symbol}|{tick}|{side}{level}") * 2 - 1) * BOOK_NOISE
            qty = max(1, round(top * grow * noise))
            offset = tick_size * (level + 1)
            price = price_krw - offset if side == "b" else price_krw + offset
            out.append(Quote(price_krw=max(tick_size, price), assumed_quantity=qty))
    return OrderBook(bids=tuple(bids), asks=tuple(asks), spread_krw=tick_size * 2)


def fill(book: OrderBook, side: str, quantity: int, reference_krw: int) -> Fill:
    """시장가 체결 — 호가를 걷어올리며 채운다.

    매수는 매도호가를 낮은 가격부터, 매도는 매수호가를 높은 가격부터 소진한다.
    호가를 다 먹고도 수량이 남으면 **마지막 호가로 나머지를 채우고** `exhausted`를 세운다 —
    체결을 거부하면 큰 주문이 영영 안 나가고, 게임에 다른 참가자가 없어 호가가 보충되지도
    않는다. 대신 그만큼 슬리피지가 커져 비용으로 드러난다.
    """
    levels = book.asks if side == "LONG" else book.bids
    remaining, notional, filled = quantity, 0, 0
    for quote in levels:
        take = min(remaining, quote.assumed_quantity)
        notional += take * quote.price_krw
        filled += take
        remaining -= take
        if remaining <= 0:
            break
    exhausted = remaining > 0
    if exhausted and levels:
        notional += remaining * levels[-1].price_krw
        filled += remaining
    if filled <= 0 or reference_krw <= 0:
        return Fill(0, reference_krw, 0.0, exhausted)
    avg = round(notional / filled)
    # 매수는 비싸질수록, 매도는 싸질수록 불리하다
    slip = (avg - reference_krw) / reference_krw if side == "LONG" else (reference_krw - avg) / reference_krw
    return Fill(
        filled_quantity=filled,
        avg_price_krw=avg,
        slippage_pct=round(slip * 100.0, 4),
        exhausted=exhausted,
    )


def vi_triggered(day_open_krw: int, price_krw: int) -> bool:
    """변동성 완화 장치 발동 여부 — 그날 시가 대비 ±10%."""
    if day_open_krw <= 0:
        return False
    return abs(price_krw - day_open_krw) / day_open_krw >= VI_TRIGGER_PCT


def halted_until(tick: int) -> int:
    """발동 시 매매가 잠기는 마지막 틱."""
    return tick + VI_HALT_TICKS


# --- 공매도 잔고 ---------------------------------------------------------------
# 밈 종목의 서사(숏스퀴즈)가 성립하려면 "얼마나 공매도가 쌓였는가"가 보여야 한다.
# 실제 시장에서도 공시되는 값이고, GME 사태의 핵심 숫자였다.
SHORT_BASE_PCT = 2.5        # 일반 종목 기준 잔고(발행주식 대비 %)
SHORT_MEME_PCT = 18.0       # 밈 종목 기준 — 실제 스퀴즈 종목이 이 수준이었다
SHORT_SWING = 0.6           # 기준 대비 흔들림 폭


def short_interest_pct(params: SymbolParams, tick: int) -> float:
    """공매도 잔고 비율(발행주식 대비 %). 게임일 단위로 천천히 움직인다.

    틱마다 흔들리면 숫자가 노이즈로 보인다 — 실제 공시도 일 단위다.
    """
    day = tick // TICKS_PER_GAME_DAY
    base = SHORT_MEME_PCT if params.meme else SHORT_BASE_PCT
    swing = (uniform("short", f"{params.symbol}|{day}") * 2 - 1) * SHORT_SWING
    return round(max(0.1, base * (1.0 + swing)), 2)
