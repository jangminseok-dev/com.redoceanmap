"""시장 이벤트 — 호재·악재 (game-strategy §3-3).

**이벤트도 결정론이다.** 유저는 "방금 뜬 뉴스"로 보지만, 서버는 과거 어느 슬롯이든 같은
목록을 재현한다 — 그래서 이벤트 로그 테이블이 필요 없다(game-harness §4-2).

문구는 **템플릿 룩업**이다. LLM을 쓰지 않는다 — 결정론 위반이고 추론 비용이 든다(§2).
종목명이 가상이라("세빛반도체") 문구가 실재 기업에 대한 서술이 되지 않는다.

가격에 미치는 영향은 두 갈래다.

- **즉시 충격** — 3틱에 걸쳐 선형으로 반영한다. 한 틱에 다 넣으면 차트가 수직선이 된다.
- **지속 드리프트** — 지수감쇠하며 며칠에 걸쳐 밀어 올리거나 끌어내린다.

두 갈래 모두 **창 경계로 갈수록 0에 수렴한다**(테이퍼). 창은 계산 비용을 일정하게 만들려고
두는 것인데, 테이퍼가 없으면 이벤트가 창을 벗어나는 순간 기여가 통째로 사라져 최대 6%짜리
역방향 점프가 생긴다 — 유저에게는 아무 뉴스도 없이 차트가 꺾이는 절벽으로 보인다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from game.domain.clock.game_epoch import SEASON_TICKS, TICKS_PER_GAME_DAY
from game.domain.market.symbol_params import SYMBOLS, SymbolParams
from game.domain.rng.deterministic import uniform

EVENT_SLOT_TICKS = 15  # 게임 6시간마다 1슬롯 = 하루 4슬롯
# 슬롯당 발생 확률 → 평균 게임 1일 1.6건. 0.25(하루 1건)에서 올렸다 —
# 종목이 12개일 때는 개별 종목에 뉴스가 자주 걸렸지만 36개가 되면서 같은 확률로는
# 한 종목이 뉴스를 만나는 주기가 3배로 늘어난다("뉴스가 안 뜬다"로 읽힌다).
EVENT_PROBABILITY = 0.40
EVENT_RAMP_TICKS = 3  # 즉시 충격을 이 틱에 나눠 반영
EVENT_WINDOW_TICKS = 300  # 게임 5일 — 이보다 오래된 이벤트는 계산에서 뺀다.
#                           가장 긴 지속(섹터 5일)을 담아야 드리프트가 정점 전에 잘리지 않는다

# 범위별 비중·강도. 밈 이벤트가 가장 세고, 시장 전체 이벤트가 가장 넓다.
_SCOPE_SYMBOL, _SCOPE_SECTOR, _SCOPE_MARKET = "symbol", "sector", "market"
_SCOPE_MEME = "meme"
_SCOPE_WEIGHTS = (
    (_SCOPE_SYMBOL, 0.58),
    (_SCOPE_SECTOR, 0.18),
    (_SCOPE_MARKET, 0.09),
    (_SCOPE_MEME, 0.15),
)
_SCOPE_SPEC = {
    # scope: (충격 최소, 충격 최대, 일간 드리프트, 지속 게임일)
    _SCOPE_SYMBOL: (0.015, 0.060, 0.0030, 3),
    _SCOPE_SECTOR: (0.010, 0.030, 0.0020, 5),
    _SCOPE_MARKET: (0.020, 0.050, 0.0040, 2),
    # 밈은 한 방이 크고 빨리 식는다 — 스퀴즈가 며칠씩 이어지면 그냥 우상향 종목이 된다.
    _SCOPE_MEME: (0.080, 0.280, 0.0060, 2),
}

# 밈 이벤트가 걸릴 종목. 없으면 밈 범위는 뽑히지 않는다(전부 일반 종목이어도 안전).
_MEME_SYMBOLS = tuple(s for s in SYMBOLS if s.meme)

_HEADLINES: dict[tuple[str, bool], tuple[str, ...]] = {
    (_SCOPE_SYMBOL, True): (
        "{name} 신규 대형 수주 공시",
        "{name} 분기 실적 시장 기대 상회",
        "{name} 신제품 초기 반응 양호",
        "{name} 해외 판로 확대 발표",
        "{name} 원가 절감 효과 가시화",
        "{name} 주요 고객사와 공급 계약 연장",
        "{name} 설비 증설 완료",
        "{name} 배당 확대 검토 보도",
    ),
    (_SCOPE_SYMBOL, False): (
        "{name} 생산 차질 발생",
        "{name} 분기 실적 시장 기대 하회",
        "{name} 주요 계약 해지 통보",
        "{name} 리콜 결정",
        "{name} 원자재 가격 부담 확대",
        "{name} 핵심 인력 대거 이탈",
        "{name} 증설 계획 철회",
        "{name} 유상증자 검토 보도",
    ),
    (_SCOPE_SECTOR, True): (
        "{name} 업황 회복 신호",
        "{name} 수요 반등 조짐",
        "{name} 정부 지원책 발표",
        "{name} 수출 지표 개선",
        "{name} 재고 조정 마무리 국면",
        "{name} 전방 산업 투자 확대",
        "{name} 규제 완화 논의",
        "{name} 글로벌 경쟁사 감산",
    ),
    (_SCOPE_SECTOR, False): (
        "{name} 업황 둔화 우려",
        "{name} 수요 위축 지속",
        "{name} 규제 강화 예고",
        "{name} 수출 지표 부진",
        "{name} 재고 누적 심화",
        "{name} 전방 산업 투자 축소",
        "{name} 원가 압박 확대",
        "{name} 공급 과잉 경고",
    ),
    (_SCOPE_MARKET, True): (
        "위험자산 선호 회복",
        "금리 인하 기대 확산",
        "기관 매수세 유입",
        "경기 지표 예상 상회",
        "환율 안정에 투자심리 개선",
        "글로벌 증시 동반 상승",
        "유동성 공급 확대 발표",
        "무역 협상 진전",
    ),
    (_SCOPE_MARKET, False): (
        "위험자산 회피 심리 확산",
        "금리 인상 우려 부각",
        "기관 매도 물량 출회",
        "경기 지표 예상 하회",
        "환율 급등에 투자심리 위축",
        "글로벌 증시 동반 조정",
        "유동성 축소 우려",
        "무역 마찰 재점화",
    ),
    # 밈 — 실적이 아니라 **수급과 화제성**이 값을 만든다. 문구도 그 축으로 쓴다.
    (_SCOPE_MEME, True): (
        "{name} 개인 매수 폭주, 숏스퀴즈 조짐",
        "{name} 커뮤니티발 매수 열풍",
        "{name} 공매도 잔고 급감…환매수 관측",
        "{name} 실시간 검색어 1위 등극",
        "{name} 유명 투자자 보유 인증에 급등",
        "{name} 거래량 평소의 40배",
        "{name} 밈 계정 언급 폭증",
        "{name} 대차잔고 소진 경고",
    ),
    (_SCOPE_MEME, False): (
        "{name} 차익 실현 물량 쏟아져",
        "{name} 유상증자로 희석 우려",
        "{name} 거래소 변동성 완화장치 발동",
        "{name} 공매도 세력 재진입 관측",
        "{name} 커뮤니티 열기 급랭",
        "{name} 신용 반대매매 경고",
        "{name} 내부자 매도 공시",
        "{name} 테마 소멸 우려 확산",
    ),
}


@dataclass(frozen=True)
class MarketEvent:
    slot: int
    tick: int  # 발생 틱
    scope: str  # symbol | sector | market
    target: str  # 종목 코드 · 섹터명 · "" (시장 전체)
    target_name: str  # 화면에 쓸 이름
    positive: bool
    shock: float  # 즉시 충격(로그 수익)
    drift_per_day: float  # 지속 드리프트
    duration_days: int
    headline: str


def _pick_scope(roll: float) -> str:
    cumulative = 0.0
    for scope, weight in _SCOPE_WEIGHTS:
        cumulative += weight
        if roll < cumulative:
            return scope
    return _SCOPE_MARKET


@lru_cache(maxsize=8192)
def event_at_slot(slot: int) -> MarketEvent | None:
    """슬롯 하나의 이벤트. 발생하지 않으면 None. 같은 슬롯은 언제 물어도 같은 결과다.

    **메모이제이션은 값을 바꾸지 않는다.** 이 함수는 `slot` 하나만 받는 순수 함수이고
    입력이 같으면 결과가 같다 — 캐시는 같은 계산을 반복하지 않을 뿐이다(가격을 저장하는
    것과 다르다, §4-2). 가격 1틱을 계산할 때마다 창 안의 20슬롯을 다시 굴리던 것이
    시리즈 240틱이면 4,800회가 된다. 시즌 전체 슬롯이 2,880개라 캐시가 무한히 늘지 않는다.
    """
    if slot < 0:
        return None
    key = str(slot)
    if uniform("evt-fire", key) >= EVENT_PROBABILITY:
        return None

    scope = _pick_scope(uniform("evt-scope", key))
    if scope == _SCOPE_MEME and not _MEME_SYMBOLS:
        scope = _SCOPE_SYMBOL  # 밈 종목이 없으면 일반 종목 이벤트로 떨어진다
    positive = uniform("evt-sign", key) < 0.5
    low, high, drift, duration = _SCOPE_SPEC[scope]
    magnitude = low + (high - low) * uniform("evt-size", key)

    if scope == _SCOPE_MEME:
        pool = _MEME_SYMBOLS
        params = pool[int(uniform("evt-target", key) * len(pool)) % len(pool)]
        target, target_name = params.symbol, params.name
    elif scope == _SCOPE_SYMBOL:
        params = SYMBOLS[int(uniform("evt-target", key) * len(SYMBOLS)) % len(SYMBOLS)]
        target, target_name = params.symbol, params.name
    elif scope == _SCOPE_SECTOR:
        groups = sorted({s.sector_group for s in SYMBOLS})
        group = groups[int(uniform("evt-target", key) * len(groups)) % len(groups)]
        target, target_name = group, group
    else:
        target, target_name = "", "시장 전체"

    templates = _HEADLINES[(scope, positive)]
    template = templates[int(uniform("evt-text", key) * len(templates)) % len(templates)]

    return MarketEvent(
        slot=slot,
        tick=slot * EVENT_SLOT_TICKS,
        scope=scope,
        target=target,
        target_name=target_name,
        positive=positive,
        shock=magnitude if positive else -magnitude,
        drift_per_day=drift if positive else -drift,
        duration_days=duration,
        headline=template.format(name=target_name),
    )


def events_in_window(
    tick: int,
    window_ticks: int = EVENT_WINDOW_TICKS,
    extra: tuple[MarketEvent, ...] = (),
) -> tuple[MarketEvent, ...]:
    """`tick` 시점에 아직 영향이 남아 있는 이벤트들(발생 순).

    창 밖은 계산에서 뺀다 — 그래서 경과 시간과 무관하게 비용이 일정하다.

    `extra`는 **유도되지 않는 이벤트**다(관리자 개입). 슬롯 난수에서 나올 수 없으므로
    호출자가 저장소에서 읽어 넘긴다. 창 필터·정렬은 생성 이벤트와 똑같이 적용한다 —
    한번 섞이면 이후 경로(영향 계산·뉴스 피드·차트 마커)가 둘을 구분하지 않는다.
    """
    end = min(max(tick, 0), SEASON_TICKS)
    first_slot = max(0, (end - window_ticks) // EVENT_SLOT_TICKS)
    last_slot = end // EVENT_SLOT_TICKS
    out = []
    for slot in range(first_slot, last_slot + 1):
        event = event_at_slot(slot)
        if event is not None and event.tick <= end:
            out.append(event)
    out.extend(e for e in extra if end - window_ticks <= e.tick <= end)
    out.sort(key=lambda e: e.tick)
    return tuple(out)


def recent_headlines(
    tick: int, limit: int = 8, extra: tuple[MarketEvent, ...] = ()
) -> tuple[MarketEvent, ...]:
    """화면용 최근 뉴스. 최신 순으로 자른다.

    테이퍼로 기여가 사라진 뉴스도 그대로 내려보낸다 — 걸러내는 대신 `event_contribution()`을
    함께 실어 화면이 "영향 소멸"로 표시하게 한다. 여기서 거르면 유저는 뉴스가 있었다는
    사실 자체를 못 본다. (창 `EVENT_WINDOW_TICKS`를 줄이는 건 별개 문제다 — 그건 가격 변조다.)
    """
    return tuple(reversed(events_in_window(tick, extra=extra)))[:limit]


def _applies_to(event: MarketEvent, params: SymbolParams) -> bool:
    if event.scope == _SCOPE_MARKET:
        return True
    if event.scope == _SCOPE_SECTOR:
        return params.sector_group == event.target
    return params.symbol == event.target  # symbol · meme 모두 종목 1개에만 걸린다


def affected_symbols(event: MarketEvent) -> tuple[str, ...]:
    """이 이벤트가 실제로 가격을 미는 종목 코드들.

    화면이 "이 뉴스가 내 종목에 걸리는가"를 판단할 유일한 근거다 — 유저가 보는 피드의
    대부분은 다른 종목 뉴스이므로, 구분이 없으면 "뉴스가 반영되지 않는다"로 읽힌다.
    """
    return tuple(s.symbol for s in SYMBOLS if _applies_to(event, s))


def event_contribution(event: MarketEvent, tick: int) -> float:
    """이벤트 1건이 `tick` 시점에 기여하는 값(로그 공간). 대상 종목 여부는 보지 않는다.

    `impact()`가 합산하는 항이며, 화면이 "지금 남은 영향"을 표시할 때도 같은 값을 쓴다 —
    보여주는 숫자와 가격에 들어가는 숫자가 갈라질 자리를 만들지 않는다.
    """
    elapsed_ticks = tick - event.tick
    if elapsed_ticks < 0:
        return 0.0
    # 즉시 충격 — 3틱에 걸쳐 선형으로 들어간다
    ramp = min(1.0, (elapsed_ticks + 1) / EVENT_RAMP_TICKS)
    # 지속 드리프트 — 지수감쇠
    elapsed_days = elapsed_ticks / TICKS_PER_GAME_DAY
    drift = (
        event.drift_per_day
        * elapsed_days
        * math.exp(-elapsed_days / event.duration_days)
    )
    # 창 경계에서 0이 되게 깎는다 — 없으면 창을 벗어나는 순간 절벽이 생긴다
    taper = max(0.0, 1.0 - elapsed_ticks / EVENT_WINDOW_TICKS)
    return (event.shock * ramp + drift) * taper


def impact(
    params: SymbolParams, tick: int, extra: tuple[MarketEvent, ...] = ()
) -> float:
    """이 종목의 `tick` 시점 이벤트 영향 합(로그 공간).

    가격 엔진이 `logP`에 더하는 항이다(game-harness §1-2의 `J`).
    `extra`(관리자 개입)도 생성 이벤트와 똑같이 더해진다.
    """
    total = 0.0
    for event in events_in_window(tick, extra=extra):
        if not _applies_to(event, params):
            continue
        total += event_contribution(event, tick)
    return total
