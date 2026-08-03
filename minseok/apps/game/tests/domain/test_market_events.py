import hashlib
import json
import statistics
import subprocess
import sys
from pathlib import Path

import game
from game.domain.clock.game_epoch import TICKS_PER_GAME_DAY
from game.domain.market import market_events as events
from game.domain.market import price_engine
from game.domain.market.symbol_params import SYMBOLS

_APPS_DIR = str(Path(game.__file__).resolve().parent.parent)


def _all_events(last_slot: int = 2_000):
    return [e for slot in range(last_slot) if (e := events.event_at_slot(slot)) is not None]


# --- 결정론 -----------------------------------------------------------------

def test_같은_슬롯은_항상_같은_이벤트다():
    for slot in (0, 7, 123, 999):
        assert events.event_at_slot(slot) == events.event_at_slot(slot)


def test_다른_프로세스에서도_같은_이벤트가_나온다():
    """내장 hash() 혼입을 잡는다 — 워커가 여러 개면 유저마다 다른 뉴스를 보게 된다."""
    expected = [e.headline for e in events.events_in_window(5_000)]
    script = (
        "from game.domain.market import market_events as e;"
        "print('|'.join(x.headline for x in e.events_in_window(5000)))"
    )
    out = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env={"PYTHONHASHSEED": "31337", "PYTHONPATH": _APPS_DIR},
        check=True,
    )
    assert out.stdout.strip().split("|") if expected else True
    assert (out.stdout.strip().split("|") if expected else []) == expected


# --- 발생 빈도 --------------------------------------------------------------

def test_평균_게임_1일에_한_건_반_안팎_발생한다():
    """슬롯당 40% × 하루 4슬롯 = 하루 1.6건. 현실로는 1시간에 1.6건이다.

    종목이 36개가 되면서 0.25(하루 1건)로는 한 종목이 뉴스를 만나는 주기가 3배로 늘었다.
    """
    slots = 4_000
    fired = len(_all_events(slots))
    per_day = fired / (slots / 4)
    assert 1.4 < per_day < 1.8


def test_범위_비중이_설계대로다():
    all_events = _all_events(4_000)
    scopes = [e.scope for e in all_events]
    ratio = {s: scopes.count(s) / len(scopes) for s in ("symbol", "sector", "market", "meme")}
    assert 0.50 < ratio["symbol"] < 0.66  # 설계 58%
    assert 0.12 < ratio["sector"] < 0.24  # 설계 18%
    assert 0.04 < ratio["market"] < 0.15  # 설계 9%
    assert 0.10 < ratio["meme"] < 0.21    # 설계 15%


def test_밈_이벤트는_밈_종목에만_걸리고_더_세다():
    """밈주식의 성격은 σ만으로 안 나온다 — 한 방에 크게 튀는 뉴스가 있어야 한다."""
    meme_names = {s.name for s in SYMBOLS if s.meme}
    assert meme_names, "밈 종목이 없으면 이 규칙 자체가 성립하지 않는다"

    all_events = _all_events(4_000)
    meme_events = [e for e in all_events if e.scope == "meme"]
    symbol_events = [e for e in all_events if e.scope == "symbol"]
    assert meme_events

    assert all(e.target_name in meme_names for e in meme_events)
    # 최소 충격조차 일반 종목 이벤트의 최대 충격보다 크다
    assert min(abs(e.shock) for e in meme_events) > max(abs(e.shock) for e in symbol_events)


def test_호재와_악재가_균형을_이룬다():
    """기대값이 한쪽으로 쏠리면 최적 전략이 고정된다."""
    all_events = _all_events(4_000)
    positive_ratio = sum(1 for e in all_events if e.positive) / len(all_events)
    assert 0.45 < positive_ratio < 0.55


# --- 문구 -------------------------------------------------------------------

def test_문구는_비어_있지_않고_가상_종목명을_쓴다():
    names = {s.name for s in SYMBOLS}
    for event in _all_events(500):
        assert event.headline
        if event.scope == "symbol":
            assert event.target_name in names


def test_시장_전체_이벤트는_종목명을_넣지_않는다():
    market = [e for e in _all_events(4_000) if e.scope == "market"]
    assert market
    assert all(e.target == "" and e.target_name == "시장 전체" for e in market)


# --- 가격 영향 --------------------------------------------------------------

def test_창_밖_이벤트는_영향을_주지_않는다():
    """경과 시간과 무관하게 비용이 일정해야 한다."""
    assert events.events_in_window(10_000, window_ticks=events.EVENT_WINDOW_TICKS)
    old = events.events_in_window(10_000)
    assert all(10_000 - e.tick <= events.EVENT_WINDOW_TICKS for e in old)


def test_즉시_충격은_여러_틱에_걸쳐_들어간다():
    """한 틱에 다 넣으면 차트가 수직선이 된다.

    `impact`가 아니라 `event_contribution`으로 본다 — impact는 그 시점 창 안의 **모든**
    이벤트 합이라 다른 뉴스가 겹치면 한 건의 램프가 가려진다. 둘이 같은 값이라는 것은
    `test_impact는_기여도의_단순_합이다`가 따로 지킨다.
    """
    event = next(e for e in _all_events(2_000) if e.scope == "symbol")
    at_fire = events.event_contribution(event, event.tick)
    at_full = events.event_contribution(event, event.tick + events.EVENT_RAMP_TICKS)
    assert abs(at_fire) < abs(at_full)


def test_해당하지_않는_종목에는_영향이_없다():
    symbol_events = [e for e in _all_events(600) if e.scope == "symbol"]
    event = symbol_events[0]
    other = next(
        s for s in SYMBOLS if s.symbol != event.target and s.sector_group != event.target
    )
    # 그 시점에 시장·섹터 이벤트가 없다면 다른 종목 영향은 0이어야 한다
    window = [e for e in events.events_in_window(event.tick) if e.scope != "symbol"]
    if not window:
        assert events.impact(other, event.tick) == 0.0


def test_섹터_이벤트는_3종목_이상에_걸린다():
    """game-strategy §3-3 표는 '섹터 3~5종목'이다.

    세부 업종(`sector`)은 종목마다 하나씩이라 그걸로 판정하면 항상 1종목만 맞는다 —
    섹터 이벤트가 종목 이벤트의 약한 복제본이 되어 유형이 하나 사라진다.
    """
    sector_events = [e for e in _all_events(2_000) if e.scope == "sector"]
    assert sector_events
    for event in sector_events:
        hit = [s for s in SYMBOLS if events._applies_to(event, s)]
        assert 3 <= len(hit) <= 5, f"{event.target}에 {len(hit)}종목"


def test_창은_가장_긴_지속기간을_담는다():
    """창이 지속기간보다 짧으면 드리프트가 정점에 닿기 전에 잘린다."""
    longest = max(spec[3] for spec in events._SCOPE_SPEC.values())
    assert events.EVENT_WINDOW_TICKS >= longest * TICKS_PER_GAME_DAY


def test_이벤트_영향은_창_경계에서_0으로_수렴한다():
    """테이퍼가 없으면 창을 벗어나는 순간 충격이 통째로 사라져 절벽이 생긴다.

    유저에게는 아무 뉴스도 없이 차트가 최대 6% 꺾이는 것으로 보인다.
    """
    event = next(e for e in _all_events(2_000) if e.scope == "symbol")
    edge = event.tick + events.EVENT_WINDOW_TICKS
    just_inside = abs(events.event_contribution(event, edge - 1))
    peak = abs(events.event_contribution(event, event.tick + events.EVENT_RAMP_TICKS))
    assert just_inside < peak * 0.05


def test_이벤트가_가격을_실제로_움직인다():
    """엔진에 연결됐는지 — 창 안팎의 가격이 달라야 한다."""
    params = SYMBOLS[0]
    moved = any(
        events.impact(params, tick) != 0.0 for tick in range(0, 3_000, events.EVENT_SLOT_TICKS)
    )
    assert moved


def test_이벤트를_넣어도_가격은_여전히_결정론이다():
    params = SYMBOLS[0]
    assert len({price_engine.price_at(params, 1_234) for _ in range(50)}) == 1


def test_이벤트_영향이_에포크_안에서_고정이다():
    """뉴스가 가격에 미치는 영향의 전 구간 지문(36종목 × 205틱 = 7,380 샘플).

    이 값이 바뀌면 진행 중인 시즌의 과거가 소급 변조된다 — **해시를 고칠 때는 반드시
    `GAME_EPOCH_ID` 승격이 함께 와야 한다**(game-harness §1-4).

    갱신 이력:
    - 에포크 1: `daaae8ff…` (12종목 · EVENT_PROBABILITY 0.25 · 범위 3종)
    - 에포크 2: 아래 값 (36종목 · 0.40 · 밈 범위 추가) — 2026-08-03
    """
    snapshot = {
        params.symbol: [round(events.impact(params, t), 12) for t in range(0, 43_200, 211)]
        for params in SYMBOLS
    }
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    assert digest == "8177f4beba6e32c9dd3b862b7bd04e247aa23ea064c9e8153b3ca3798cced0e0"


def test_impact는_기여도의_단순_합이다():
    """화면에 보여줄 기여도와 가격에 들어가는 값이 갈라질 자리를 없앤다."""
    params = SYMBOLS[0]
    for tick in (500, 1_200, 3_000, 12_000):
        expected = sum(
            events.event_contribution(e, tick)
            for e in events.events_in_window(tick)
            if events._applies_to(e, params)
        )
        assert events.impact(params, tick) == expected


def test_영향_종목_목록이_범위와_일치한다():
    """scope가 약속한 범위를 `affected_symbols()`가 그대로 돌려줘야 한다.

    화면은 이 목록만 보고 "내 종목 뉴스"를 가른다 — 범위가 어긋나면 관계없는 뉴스가
    내 종목 것으로 표시된다.
    """
    for event in _all_events(3_000):
        affected = events.affected_symbols(event)
        if event.scope in ("symbol", "meme"):
            assert affected == (event.target,)
        elif event.scope == "sector":
            assert len(affected) >= 3  # 섹터 그룹은 3종목 이상(§3-3)
            assert all(
                next(s for s in SYMBOLS if s.symbol == code).sector_group == event.target
                for code in affected
            )
        else:
            assert len(affected) == len(SYMBOLS)  # 시장 전체


def test_이벤트가_기대값이_아니라_분산을_키운다():
    """호재·악재가 균형이라 중앙값은 그대로고 폭만 넓어져야 한다."""
    daily = []
    for params in SYMBOLS[:6]:
        for day in range(1, 200):
            before = price_engine.price_at(params, (day - 1) * TICKS_PER_GAME_DAY)
            after = price_engine.price_at(params, day * TICKS_PER_GAME_DAY)
            daily.append((after - before) / before)
    assert abs(statistics.fmean(daily)) < 0.01  # 기대값은 0 근처
    assert statistics.pstdev(daily) > 0.01  # 변동은 살아 있다
