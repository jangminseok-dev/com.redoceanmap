import pytest

from game.domain.market import indicators


def test_이동평균은_표본이_찰_때부터_나온다():
    """앞 구간을 0으로 채우면 차트가 바닥에서 치솟는 가짜 선을 그린다."""
    ma = indicators.moving_average([10, 20, 30, 40], 3)
    assert ma[:2] == [None, None]
    assert ma[2] == pytest.approx(20.0)   # (10+20+30)/3
    assert ma[3] == pytest.approx(30.0)   # (20+30+40)/3


def test_표본보다_기간이_길면_전부_None이다():
    assert indicators.moving_average([1, 2], 5) == [None, None]


def test_이동평균_길이는_입력과_같다():
    """봉 배열과 인덱스가 맞아야 차트가 같은 x에 그린다."""
    closes = list(range(200))
    for period in indicators.MA_PERIODS:
        assert len(indicators.moving_average(closes, period)) == len(closes)


def test_이동평균은_증분_계산과_전량_계산이_같다():
    """슬라이딩 윈도 갱신에서 오차가 쌓이면 긴 구간에서 선이 어긋난다."""
    closes = [1000 + (i * 37) % 500 for i in range(300)]
    ma = indicators.moving_average(closes, 20)
    for i in range(19, len(closes)):
        assert ma[i] == pytest.approx(sum(closes[i - 19 : i + 1]) / 20)


def test_RSI는_상승만_있으면_100_하락만_있으면_0이다():
    up = indicators.rsi(list(range(1, 40)))
    down = indicators.rsi(list(range(40, 1, -1)))
    assert up[-1] == pytest.approx(100.0)
    assert down[-1] == pytest.approx(0.0)


def test_RSI는_0에서_100_사이다():
    closes = [1000 + (i * 137) % 700 for i in range(300)]
    values = [v for v in indicators.rsi(closes) if v is not None]
    assert values
    assert all(0.0 <= v <= 100.0 for v in values)


def test_RSI는_기간만큼_앞이_비어_있다():
    closes = list(range(1, 40))
    values = indicators.rsi(closes, period=14)
    assert values[:14] == [None] * 14
    assert values[14] is not None
    assert len(values) == len(closes)


def test_잘못된_기간은_거부한다():
    with pytest.raises(ValueError):
        indicators.moving_average([1, 2, 3], 0)
    with pytest.raises(ValueError):
        indicators.rsi([1, 2, 3], 0)
