"""매물대 산출 — 프론트 volumeProfile.ts와 같은 수치가 나와야 한다.

차트가 보여주는 밀집 구간과 챗이 말하는 구간이 다르면 둘 다 못 믿는다.
"""
from datetime import UTC, datetime, timedelta

from stock.domain.entities.price_bar import PriceBar
from stock.domain.services.volume_profile import (
    MIN_BARS,
    VOLUME_PROFILE_BINS,
    compute_volume_profile,
)


def _bar(i: int, low: float, high: float, close: float, volume: int) -> PriceBar:
    return PriceBar(
        ticker="TEST", timeframe="1d",
        ts=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i),
        open=close, high=high, low=low, close=close, volume=volume,
    )


def test_표본이_부족하면_산출하지_않는다():
    bars = [_bar(i, 100, 110, 105, 1000) for i in range(MIN_BARS - 1)]
    assert compute_volume_profile(bars, price=105) is None


def test_가격이_한_점에_붙어_있으면_분포가_성립하지_않는다():
    bars = [_bar(i, 100, 100, 100, 1000) for i in range(10)]
    assert compute_volume_profile(bars, price=100) is None


def test_거래량이_0이면_산출하지_않는다():
    bars = [_bar(i, 100, 110, 105, 0) for i in range(10)]
    assert compute_volume_profile(bars, price=105) is None


def test_거래량이_몰린_구간이_POC로_잡힌다():
    # 대표가 (고+저+종)/3 기준으로 200 근처에 거래량을 몰아준다.
    bars = [_bar(i, 100, 300, 200, 100) for i in range(5)]          # 대표가 200
    bars += [_bar(10 + i, 100, 300, 200, 10_000) for i in range(5)]  # 같은 구간에 대량
    profile = compute_volume_profile(bars, price=200)
    assert profile is not None
    assert profile.poc_low <= 200 <= profile.poc_high
    assert profile.poc_share == 1.0      # 전부 같은 구간에 들어갔다
    assert profile.price_position == "inside"
    assert profile.bars == 10


def test_현재가가_POC_바깥이면_위아래를_구분한다():
    bars = [_bar(i, 100, 100 + 2 * i, 100 + i, 1000) for i in range(20)]
    profile = compute_volume_profile(bars, price=1_000_000)
    assert profile is not None and profile.price_position == "above"

    profile_below = compute_volume_profile(bars, price=0.01)
    assert profile_below is not None and profile_below.price_position == "below"


def test_구간_수는_프론트와_같은_24다():
    # 화면과 다른 수치가 나오면 안 된다 — 프론트 VOLUME_PROFILE_BINS와 같은 값을 유지한다.
    assert VOLUME_PROFILE_BINS == 24
