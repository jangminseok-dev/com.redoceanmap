import pytest

from game.domain.trading.limit_fill import is_expired, resolve_fill


def _prices(series: dict[int, int]):
    """틱 → 가격 표를 가격 함수로 바꾼다(없는 틱은 마지막 값 유지)."""
    def price_of(tick: int) -> int:
        return series.get(tick, series[max(k for k in series if k <= tick)])

    return price_of


def test_le는_지정가_이하로_내려온_첫_틱에_체결된다():
    hit = resolve_fill(
        _prices({0: 10_000, 1: 9_900, 2: 9_400, 3: 9_000}),
        trigger="le",
        limit_price_krw=9_500,
        placed_tick=0,
        now_tick=3,
        expires_tick=180,
    )
    assert hit is not None and hit.tick == 2


def test_ge는_지정가_이상으로_올라온_첫_틱에_체결된다():
    hit = resolve_fill(
        _prices({0: 10_000, 1: 10_400, 2: 10_600}),
        trigger="ge",
        limit_price_krw=10_500,
        placed_tick=0,
        now_tick=2,
        expires_tick=180,
    )
    assert hit is not None and hit.tick == 2


def test_체결가는_그_틱의_가격이_아니라_지정가다():
    """유리한 갭을 유저 몫으로 주지 않는다 — 멀리 걸수록 이득이 되는 구조를 막는다."""
    hit = resolve_fill(
        _prices({0: 10_000, 1: 8_000}),  # 지정가보다 한참 아래로 떨어져도
        trigger="le",
        limit_price_krw=9_500,
        placed_tick=0,
        now_tick=1,
        expires_tick=180,
    )
    assert hit is not None and hit.price_krw == 9_500


def test_주문을_건_틱_자체는_판정하지_않는다():
    """접수 시점 가격이 이미 조건을 만족해도 그건 시장가 주문이지 예약이 아니다."""
    assert (
        resolve_fill(
            _prices({0: 9_000, 1: 9_800}),
            trigger="le",
            limit_price_krw=9_500,
            placed_tick=0,
            now_tick=1,
            expires_tick=180,
        )
        is None
    )


def test_만료_틱까지만_훑는다():
    series = _prices({0: 10_000, 1: 10_000, 2: 10_000, 3: 9_000})
    # 만료 이후에 조건이 걸렸으므로 체결되지 않는다
    assert (
        resolve_fill(
            series, trigger="le", limit_price_krw=9_500,
            placed_tick=0, now_tick=5, expires_tick=2,
        )
        is None
    )
    # 만료 틱에 걸린 것은 유효하다 (경계 포함)
    hit = resolve_fill(
        series, trigger="le", limit_price_krw=9_500,
        placed_tick=0, now_tick=5, expires_tick=3,
    )
    assert hit is not None and hit.tick == 3


def test_아직_안_지난_구간은_보지_않는다():
    """미래 틱 조회 금지(harness §1-6) — now_tick 이후는 스캔 범위 밖이다."""
    assert (
        resolve_fill(
            _prices({0: 10_000, 1: 10_000, 5: 9_000}),
            trigger="le", limit_price_krw=9_500,
            placed_tick=0, now_tick=1, expires_tick=180,
        )
        is None
    )


def test_알_수_없는_트리거는_거부한다():
    with pytest.raises(ValueError):
        resolve_fill(
            _prices({0: 1}), trigger="lt", limit_price_krw=1,
            placed_tick=0, now_tick=1, expires_tick=2,
        )


def test_만료_판정은_경계를_포함한다():
    assert is_expired(180, 180) is True
    assert is_expired(179, 180) is False


def test_스캔_비용은_만료로_묶인다():
    """만료가 없으면 장기 미접속자의 판정이 전 구간 순회가 된다 — 성능 계약."""
    calls = []

    def counting(tick: int) -> int:
        calls.append(tick)
        return 10_000

    resolve_fill(
        counting, trigger="le", limit_price_krw=1,
        placed_tick=0, now_tick=14_400, expires_tick=180,  # 10일 미접속
    )
    assert len(calls) == 180  # 14,400이 아니라 만료 길이만큼만
