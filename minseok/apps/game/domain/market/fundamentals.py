"""가상 기업 재무 — 어닝 캘린더와 PER·PBR·ROE (game-strategy §13-3).

11단계에서 **일부러 보류했던** 값들이다. 당시 근거는 "실적 개념이 게임에 없어 지어내면
의미 없는 숫자"였고, 해법으로 §13-3이 "어닝 캘린더를 먼저 도입한 뒤 파생시킨다"를 적어뒀다.
이 파일이 그 어닝 캘린더다.

**핵심 설계: 실적은 가격과 독립으로 생성한다.**
가격에서 역산하면 PER이 언제나 같은 값이 되어 아무 정보가 없다. 실적을 따로 만들고 PER·PBR을
**둘의 비율**로 내야 "많이 올라서 비싸졌다 / 실적이 나와서 싸졌다"가 성립한다.

**분기마다 갱신된다.** 게임 1분기 = 90 게임일이고 시즌은 8분기다(`game_epoch`). 분기가
바뀌는 순간 EPS가 새로 발표되므로 PER이 점프한다 — 실제 어닝 시즌과 같은 리듬이다.

**상태 = 시각의 함수**(harness §1-A). 저장하지 않고 `f(에포크, 분기, 종목)`으로 매번
재현한다. 그래서 재무제표 테이블이 없다.

⚠️ 전부 **가정치**다(§5-1). 실재 기업의 재무가 아니며 종목명도 가상이다.
"""
from __future__ import annotations

from dataclasses import dataclass

from game.domain.clock.game_epoch import (
    GAME_DAYS_PER_QUARTER,
    QUARTERS_PER_SEASON,
    TICKS_PER_GAME_DAY,
)
from game.domain.market.market_events import MarketEvent
from game.domain.market.symbol_params import SymbolParams
from game.domain.rng.deterministic import uniform

# 업종 묶음별 기준 재무 — (기준 PER, 기준 ROE, 부채비율).
# 실제 시장의 업종 특성을 그대로 옮겼다: 성장 업종은 PER이 높고, 금융은 부채비율이 원래
# 크며(예금이 부채다), 에너지·소재는 PER이 낮다.
# 밈은 **적자**다(기준 ROE가 음수) — GME·AMC가 그랬듯 PER이 아예 존재하지 않는 상태를
# 재현한다. "PER 없음"이 화면에 뜨는 것 자체가 그 종목의 성격을 말해준다.
_BY_GROUP: dict[str, tuple[float, float, float]] = {
    "반도체·AI": (22.0, 0.14, 0.6),
    "소프트웨어·플랫폼": (35.0, 0.18, 0.3),
    "헬스케어·바이오": (28.0, 0.09, 0.4),
    "모빌리티·우주": (18.0, 0.08, 0.9),
    "에너지·소재": (9.0, 0.07, 1.1),
    "소비·유통": (12.0, 0.10, 0.7),
    "통신·미디어": (14.0, 0.09, 0.8),
    "금융·핀테크": (7.0, 0.09, 3.5),
    "밈·테마": (18.0, -0.05, 1.5),
}
_DEFAULT = (15.0, 0.09, 0.8)

# 분기 실적의 결정론 흔들림. ±45%면 "기대 상회/하회"가 눈에 보일 만큼 벌어진다.
EARNINGS_NOISE = 0.45
# 분기당 기저 성장률 — 시즌 8분기 동안 완만히 는다(밈은 이 성장이 적자를 키운다).
GROWTH_PER_QUARTER = 0.03
# 서프라이즈 판정 임계 — 직전 분기 대비 이만큼 벌어지면 "상회/하회"로 부른다.
SURPRISE_THRESHOLD = 0.15


@dataclass(frozen=True)
class Fundamentals:
    """한 종목의 한 분기 재무. 금액은 전부 원이고 **가정치**다."""

    game_quarter: int
    assumed_shares_outstanding: int
    assumed_eps_krw: int          # 연환산 주당순이익. 음수면 적자다
    assumed_bps_krw: int          # 주당순자산
    assumed_roe: float            # 연환산순이익 ÷ 자본
    assumed_debt_ratio: float     # 부채 ÷ 자본
    assumed_net_income_krw: int   # 연환산 순이익
    surprise: str                 # beat | miss | inline — 직전 분기 대비


@dataclass(frozen=True)
class Valuation:
    """현재가와 재무를 엮은 값. 가격이 움직이면 이쪽만 바뀐다."""

    market_cap_krw: int
    per: float | None   # 적자면 None — 지어내지 않는다
    pbr: float | None


def _anchor(params: SymbolParams) -> tuple[float, float, float]:
    return _BY_GROUP.get(params.sector_group, _DEFAULT)


def shares_outstanding(params: SymbolParams) -> int:
    """발행주식수. 기준 시가총액이 업종·주가와 어울리게 결정론으로 정한다.

    주가가 낮은 종목이 주식수도 적으면 시가총액이 우스워진다 — 목표 시총을 먼저 잡고
    주가로 나눈다.
    """
    # 목표 시총 2,000억 ~ 12조. 종목마다 고정이고 시즌 내내 변하지 않는다.
    target_cap = 2e11 + uniform("shares", params.symbol) * 1.18e13
    return max(1_000, round(target_cap / max(1, params.base_price_krw) / 1_000) * 1_000)


def _quarter_eps(params: SymbolParams, quarter: int) -> float:
    """그 분기에 발표되는 **연환산 EPS**. 기준가와 기준 PER에서 출발한다."""
    base_per, _, _ = _anchor(params)
    base_eps = params.base_price_krw / base_per
    growth = 1.0 + GROWTH_PER_QUARTER * (quarter - 1)
    noise = 1.0 + (uniform("earnings", f"{params.symbol}|{quarter}") * 2 - 1) * EARNINGS_NOISE
    eps = base_eps * growth * noise
    _, base_roe, _ = _anchor(params)
    return -eps if base_roe < 0 else eps  # 적자 업종은 부호를 뒤집는다


def _surprise(params: SymbolParams, quarter: int) -> str:
    """직전 분기 대비 판정. 1분기는 비교 대상이 없어 `inline`이다."""
    if quarter <= 1:
        return "inline"
    now = _quarter_eps(params, quarter)
    before = _quarter_eps(params, quarter - 1)
    if before == 0:
        return "inline"
    change = (now - before) / abs(before)
    if change >= SURPRISE_THRESHOLD:
        return "beat"
    if change <= -SURPRISE_THRESHOLD:
        return "miss"
    return "inline"


def at_quarter(params: SymbolParams, game_quarter: int) -> Fundamentals:
    """그 분기에 공시된 재무. 같은 (종목, 분기)면 언제 물어도 같다."""
    quarter = max(1, min(game_quarter, QUARTERS_PER_SEASON))
    base_per, base_roe, debt_ratio = _anchor(params)
    shares = shares_outstanding(params)

    eps = _quarter_eps(params, quarter)
    # 자본은 기준 ROE에서 역산한 뒤 **직전 분기들의 이익을 누적**한다 — 흑자면 자본이
    # 늘어 ROE가 서서히 낮아지고, 적자면 자본이 깎인다(밈 종목이 그렇게 망가진다).
    base_bps = params.base_price_krw / base_per / abs(base_roe) if base_roe else 0.0
    retained = sum(_quarter_eps(params, q) / 4.0 for q in range(1, quarter))
    bps = max(1.0, base_bps + retained)

    return Fundamentals(
        game_quarter=quarter,
        assumed_shares_outstanding=shares,
        assumed_eps_krw=round(eps),
        assumed_bps_krw=round(bps),
        assumed_roe=round(eps / bps, 4),
        assumed_debt_ratio=debt_ratio,
        assumed_net_income_krw=round(eps * shares),
        surprise=_surprise(params, quarter),
    )


def value_at(params: SymbolParams, price_krw: int, financials: Fundamentals) -> Valuation:
    """현재가로 매긴 밸류에이션.

    **적자면 PER을 만들지 않는다**(`None`). 음수 PER은 화면에서 "싸다"로 오독되고,
    실제 증권 앱도 적자 종목은 PER 칸을 비운다.
    """
    per = (
        price_krw / financials.assumed_eps_krw
        if financials.assumed_eps_krw > 0
        else None
    )
    pbr = (
        price_krw / financials.assumed_bps_krw
        if financials.assumed_bps_krw > 0
        else None
    )
    return Valuation(
        market_cap_krw=price_krw * financials.assumed_shares_outstanding,
        per=round(per, 2) if per is not None else None,
        pbr=round(pbr, 2) if pbr is not None else None,
    )


# --- 어닝이 가격을 움직인다 ----------------------------------------------------
# 실측(2026-08-03)에서 분기 경계 전후 가격 변동과 EPS 변화의 상관이 **-0.028**이었다 —
# 재무는 있는데 가격과 완전한 무관계였다. 실제 시장에서 어닝은 가장 큰 개별 종목
# 이벤트이므로, 서프라이즈 크기에 비례하는 충격을 분기 경계에 넣는다.
EARNINGS_SHOCK_MAX = 0.13   # 서프라이즈가 클 때의 즉시 충격 상한(±13%)
EARNINGS_DRIFT = 0.0025     # 발표 후 표류(PEAD) — 실제 시장의 잘 알려진 성질이다
EARNINGS_DURATION_DAYS = 3

_HEADLINE = {
    "beat": "{name} 분기 실적 시장 기대 상회",
    "miss": "{name} 분기 실적 시장 기대 하회",
    "inline": "{name} 분기 실적 시장 예상 부합",
}


def earnings_events(params: SymbolParams) -> tuple[MarketEvent, ...]:
    """시즌 전체의 어닝 이벤트. 분기 경계(90 게임일)에 하나씩 선다.

    충격 크기는 **직전 분기 대비 EPS 변화율**에 비례한다 — 균등난수로 뽑으면 화면의
    "기대 상회"와 가격이 따로 논다. 부합(inline)이면 충격이 0에 가깝고, 그래도 발표
    자체가 뉴스라 헤드라인은 남는다.

    발표 후 며칠에 걸친 표류(drift)를 함께 넣는다 — 실제 시장의 PEAD(post-earnings
    announcement drift)이고, 게임에서는 "실적 발표 뒤 며칠 더 간다"는 리듬이 된다.
    """
    out = []
    for quarter in range(2, QUARTERS_PER_SEASON + 1):
        now = _quarter_eps(params, quarter)
        before = _quarter_eps(params, quarter - 1)
        if before == 0:
            continue
        change = (now - before) / abs(before)
        # ±50% 변화를 상한으로 본다. 그 이상은 이미 방향이 분명하다
        magnitude = max(-1.0, min(1.0, change / 0.5))
        surprise = _surprise(params, quarter)
        tick = (quarter - 1) * GAME_DAYS_PER_QUARTER * TICKS_PER_GAME_DAY
        out.append(
            MarketEvent(
                # 생성 이벤트(양수)·관리자 개입(음수)과 겹치지 않는 슬롯 공간
                slot=-1_000_000 - quarter,
                tick=tick,
                scope="symbol",
                target=params.symbol,
                target_name=params.name,
                positive=magnitude >= 0,
                shock=EARNINGS_SHOCK_MAX * magnitude,
                drift_per_day=EARNINGS_DRIFT * magnitude,
                duration_days=EARNINGS_DURATION_DAYS,
                headline=_HEADLINE[surprise].format(name=params.name),
            )
        )
    return tuple(out)
