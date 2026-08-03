"""관리자 주가 개입 — 유도되지 않는 유일한 시장 이벤트 (game-harness §1-A 예외).

이 게임의 모든 상태는 `f(에포크, 틱)`으로 계산되고 저장되지 않는다. 개입은 **관리자의 의도**라
난수에서 유도할 수 없으므로 저장할 수밖에 없다. 그래서 예외를 두되, 예외의 범위를 좁힌다.

**과거는 절대 바뀌지 않는다.** 개입은 만들어진 시점(`from_tick` = 그때의 현재 틱)부터만
효력이 있다. `from_tick` 이전 틱을 조회하면 기여가 0이므로 이미 체결된 체결가·분기 결산·
차트가 소급 변조되지 않는다. 저장된 것이 있어도 "같은 틱을 다시 물으면 같은 값"은 유지된다.

**취소·삭제가 없다.** 행을 지우면 그 개입이 걸려 있던 구간의 과거 가격이 바뀐다. 개입은 이벤트
창(게임 5일) 안에서 테이퍼로 저절로 소멸하고, 잘못 넣었으면 **반대 방향 개입**으로 정정한다.

**형태는 기존 뉴스와 같다.** 즉시 충격 + 지수감쇠 드리프트 + 창 경계 테이퍼. 새 계산 경로를
만들지 않고 `MarketEvent`로 변환해 같은 파이프라인에 흘려보낸다 — 그래야 가격·뉴스 피드·
차트 마커·"이 뉴스가 내 종목에 걸리는가" 판정이 전부 저절로 일관된다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from game.domain.clock.game_epoch import TICKS_PER_GAME_DAY
from game.domain.market.market_events import EVENT_WINDOW_TICKS, MarketEvent

# 관리자 입력 상한 — 실수로 0을 하나 더 붙였을 때 시즌이 즉사하지 않게 둔다.
MAX_SHOCK_PCT = 300.0         # 즉시 충격 ±300%
MAX_DRIFT_PCT_PER_DAY = 20.0  # 지속 드리프트 ±20%/게임일
# 이벤트 창(EVENT_WINDOW_TICKS = 게임 5일)을 넘길 수 없다 — 창 밖은 계산에서 빠지므로
# 6일을 넣어도 5일에서 잘린다. 화면이 지키지 못할 약속을 하지 않게 여기서 막는다.
MAX_DURATION_DAYS = EVENT_WINDOW_TICKS // TICKS_PER_GAME_DAY

SCOPE_SYMBOL, SCOPE_SECTOR, SCOPE_MARKET = "symbol", "sector", "market"
SCOPES = (SCOPE_SYMBOL, SCOPE_SECTOR, SCOPE_MARKET)


@dataclass(frozen=True)
class PriceIntervention:
    """저장된 개입 한 건. 퍼센트는 **사람이 읽는 값**이고 로그 변환은 이 파일에서만 한다."""

    id: int
    epoch_id: int
    scope: str            # symbol | sector | market
    target: str           # 종목 코드 · 묶음 업종명 · "" (시장 전체)
    target_name: str
    from_tick: int        # 개입이 걸리기 시작하는 틱 = 생성 시점의 현재 틱
    shock_pct: float      # 즉시 충격(%) — 부호가 호재·악재를 가른다
    drift_pct_per_day: float
    duration_days: int
    headline: str         # 유저에게 보이는 문구. 일반 뉴스와 구분되지 않는다
    note: str | None = None  # 관리자 메모(비공개). 가격 계산에는 쓰이지 않는다


def validate(shock_pct: float, drift_pct_per_day: float, duration_days: int, scope: str) -> None:
    """관리자 입력 검증. 위반이면 `ValueError` — 라우터가 400으로 옮긴다."""
    if scope not in SCOPES:
        raise ValueError(f"범위는 {' · '.join(SCOPES)} 중 하나여야 합니다")
    if abs(shock_pct) > MAX_SHOCK_PCT:
        raise ValueError(f"즉시 충격은 ±{MAX_SHOCK_PCT:g}% 이내여야 합니다")
    if abs(drift_pct_per_day) > MAX_DRIFT_PCT_PER_DAY:
        raise ValueError(f"지속 드리프트는 ±{MAX_DRIFT_PCT_PER_DAY:g}%/게임일 이내여야 합니다")
    if not 1 <= duration_days <= MAX_DURATION_DAYS:
        raise ValueError(f"지속 기간은 1~{MAX_DURATION_DAYS} 게임일이어야 합니다")
    if shock_pct == 0 and drift_pct_per_day == 0:
        raise ValueError("즉시 충격과 지속 드리프트가 둘 다 0이면 개입이 아닙니다")


def shock_pct_for_target_price(current_krw: int, target_krw: int) -> float:
    """현재가를 목표가로 옮기는 즉시 충격(%).

    관리자에게는 "이 종목을 10만원으로"가 "몇 % 올릴까"보다 자연스럽다. 가격이 로그정규라
    단순 비율이 곧 충격이 되므로 변환은 나눗셈 하나다. 상한 검증은 `validate`가 맡는다.
    """
    if current_krw <= 0 or target_krw <= 0:
        raise ValueError("가격은 1원 이상이어야 합니다")
    return (target_krw / current_krw - 1.0) * 100.0


def to_event(intervention: PriceIntervention) -> MarketEvent:
    """저장된 개입을 시장 이벤트로. 여기서 퍼센트가 로그 공간으로 넘어간다.

    `slot`은 음수(-id)를 쓴다 — 생성 이벤트의 슬롯 번호와 겹치지 않게 하려는 것이고,
    슬롯은 재현 키일 뿐 가격 계산에는 쓰이지 않는다.
    """
    return MarketEvent(
        slot=-intervention.id,
        tick=intervention.from_tick,
        scope=intervention.scope,
        target=intervention.target,
        target_name=intervention.target_name,
        positive=intervention.shock_pct + intervention.drift_pct_per_day >= 0,
        shock=math.log1p(intervention.shock_pct / 100.0),
        drift_per_day=math.log1p(intervention.drift_pct_per_day / 100.0),
        duration_days=intervention.duration_days,
        headline=intervention.headline,
    )


def to_events(interventions: tuple[PriceIntervention, ...]) -> tuple[MarketEvent, ...]:
    return tuple(to_event(i) for i in interventions)
