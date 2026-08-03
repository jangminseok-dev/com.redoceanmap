"""상태 분해 검증. **부호 규약(양수=뜨겁다)이 이 파일의 핵심 회귀 대상이다.**"""
import pytest

from game.domain.market import signal


def _evaluate(**overrides):
    base = dict(
        price_krw=100_000,
        ma_short=100_000.0,
        ma_long=100_000.0,
        rsi=50.0,
        percent_b=0.5,
        volume_ratio=1.0,
        obv_slope=0.0,
        news_impact_log=0.0,
        headline_count=0,
    )
    base.update(overrides)
    return signal.evaluate(**base)


def _axis(result, key):
    return next(a for a in result.axes if a.key == key)


# --- 부호 규약 --------------------------------------------------------------

def test_모든_축이_같은_방향을_가리킨다():
    """정배열·과매수·밴드상단·매수유입·호재는 **전부 양수**여야 한다.

    첫 구현이 추세는 '정배열=강세', RSI는 '과매수=되돌림'으로 섞어 써서 두 축이 서로를
    상쇄했다 — 명백한 과열 종목이 '눌림'으로 나왔다.
    """
    hot = _evaluate(
        ma_short=105_000.0,
        ma_long=100_000.0,
        price_krw=106_000,
        rsi=85.0,
        percent_b=0.97,
        volume_ratio=2.0,
        obv_slope=0.4,
        news_impact_log=0.10,
        headline_count=3,
    )
    assert all(a.value > 0 for a in hot.axes), [(a.key, a.value) for a in hot.axes]
    assert hot.score > 0.35
    assert hot.label == "과열"


def test_반대쪽도_전부_음수다():
    cold = _evaluate(
        ma_short=95_000.0,
        ma_long=100_000.0,
        price_krw=94_000,
        rsi=15.0,
        percent_b=0.03,
        volume_ratio=2.0,
        obv_slope=-0.4,
        news_impact_log=-0.10,
        headline_count=2,
    )
    assert all(a.value < 0 for a in cold.axes), [(a.key, a.value) for a in cold.axes]
    assert cold.score < -0.35
    assert cold.label == "침체"


def test_중립_입력은_잠잠이다():
    assert _evaluate().label == "잠잠"


# --- 축 개별 ----------------------------------------------------------------

def test_점수는_항상_범위_안이다():
    for rsi in (0.0, 30.0, 50.0, 70.0, 100.0):
        for pb in (0.0, 0.5, 1.0):
            for news in (-1.0, 0.0, 1.0):
                r = _evaluate(rsi=rsi, percent_b=pb, news_impact_log=news)
                assert -1.0 <= r.score <= 1.0
                assert all(-1.0 <= a.value <= 1.0 for a in r.axes)


def test_뉴스_기여가_클수록_뉴스축이_커진다():
    weak = _axis(_evaluate(news_impact_log=0.01, headline_count=1), "news")
    strong = _axis(_evaluate(news_impact_log=0.10, headline_count=1), "news")
    assert strong.value > weak.value


def test_뉴스_한_방이_다른_축을_전부_덮지_않는다():
    """밈 스퀴즈(즉시 28%)가 들어와도 뉴스축은 포화될 뿐 가중치를 넘지 않는다."""
    squeeze = _evaluate(news_impact_log=0.25, headline_count=1)
    assert _axis(squeeze, "news").value == pytest.approx(1.0)
    assert squeeze.score < signal.WEIGHT_NEWS + 0.01  # 나머지 축이 0이면 가중치가 상한


def test_거래가_터져도_방향이_없으면_수급축은_0에_가깝다():
    flat = _axis(_evaluate(volume_ratio=3.0, obv_slope=0.0), "flow")
    assert flat.value == pytest.approx(0.0)


# --- 표본 부족 --------------------------------------------------------------

def test_계산할_수_없는_축은_가중치까지_빠진다():
    """0으로 채우면 시즌 초반에 모든 종목이 중립으로 보인다."""
    early = _evaluate(ma_short=None, ma_long=None, rsi=None, percent_b=None,
                      volume_ratio=None, obv_slope=None,
                      news_impact_log=0.10, headline_count=2)
    assert [a.key for a in early.axes] == ["news"]
    # 뉴스 하나만 남았으면 그 축이 점수를 그대로 정한다(가중치로 눌리지 않는다)
    assert early.score == pytest.approx(_axis(early, "news").value, abs=1e-4)


def test_가중치_합은_1이다():
    total = (
        signal.WEIGHT_TREND + signal.WEIGHT_MOMENTUM + signal.WEIGHT_POSITION
        + signal.WEIGHT_FLOW + signal.WEIGHT_NEWS
    )
    assert total == pytest.approx(1.0)
