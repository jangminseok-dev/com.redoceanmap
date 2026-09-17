import math
import random

import pandas as pd

from stock.domain.services import risk_signal as rs
from stock.domain.services.risk_signal_backtester import RiskObservation, RiskSignalBacktester


def _series(n=700, seed=7):
    rnd = random.Random(seed)
    price, out = 100.0, []
    for i in range(n):
        vol = 0.03 if 300 <= i < 360 else 0.01          # 중간에 변동성 확대 구간
        price *= math.exp(rnd.gauss(0.0004, vol))
        out.append(price)
    return out


def test_증분_계산은_pandas_정의와_같다():
    closes = _series()
    s = pd.Series(closes)
    r = (s / s.shift(1)).apply(math.log)
    rv = r.rolling(20).std() * math.sqrt(252)
    pct = rv.rolling(252, min_periods=200).rank(pct=True)
    q70 = rv.rolling(252, min_periods=200).quantile(0.7)
    got = rs.states(closes)
    for i in (450, 520, 699):
        assert got[i] is not None
        assert math.isclose(got[i].rv20, rv[i], rel_tol=1e-9)
        assert math.isclose(got[i].rv_percentile, pct[i], rel_tol=1e-9)
        assert math.isclose(got[i].rv_q70, q70[i], rel_tol=1e-9)


def test_변동성_급등_직후는_HIGH_잠잠하면_LOW에_가깝다():
    closes = _series()
    got = rs.states(closes)
    assert got[330].vol_state == "HIGH"
    assert got[299] is None or got[299].vol_state != "HIGH" or got[299].rv_percentile < 0.95


def test_봉이_모자라면_판정하지_않는다():
    assert rs.state_at(_series(n=150)) is None
    assert rs.state_at(_series()) is not None


def test_검증은_두_구간_모두_기준과_갈라져야_한다():
    def obs(period, state, hit, n):
        return [RiskObservation(period, state, "NORMAL", hit, False) for _ in range(n)]
    strong = (obs("train", "HIGH", True, 4000) + obs("train", "NORMAL", False, 16000)
              + obs("test", "HIGH", True, 4000) + obs("test", "NORMAL", False, 16000))
    payload = RiskSignalBacktester().aggregate(strong, train_end_year=2020, first_date="a", last_date="b", tickers=1)
    vol_high = next(s for s in payload["signals"] if s["key"] == "vol_high")
    assert vol_high["validated"] and vol_high["test"]["n_eff"] == 200.0
    # 검증 구간에서 사라지면 검증 미달
    faded = (obs("train", "HIGH", True, 4000) + obs("train", "NORMAL", False, 16000)
             + obs("test", "HIGH", False, 4000) + obs("test", "NORMAL", False, 16000))
    payload = RiskSignalBacktester().aggregate(faded, train_end_year=2020, first_date="a", last_date="b", tickers=1)
    assert not next(s for s in payload["signals"] if s["key"] == "vol_high")["validated"]
