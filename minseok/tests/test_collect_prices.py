"""collect_prices.fetch_bars — 어느 봉을 '완성'으로 보고 담는가(네트워크 없음, yfinance는 스텁)."""
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(_SCRIPTS))   # 스크립트가 같은 폴더의 collect_news를 import한다
_spec = importlib.util.spec_from_file_location("collect_prices", _SCRIPTS / "collect_prices.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


class _Ticker:
    def __init__(self, frame):
        self._frame = frame

    def history(self, **_):
        return self._frame


def _frame(starts):
    index = pd.DatetimeIndex(starts)
    return pd.DataFrame({"Open": 1.0, "High": 2.0, "Low": 0.5, "Close": 1.5, "Volume": 100}, index=index)


def _fetch(monkeypatch, ticker, timeframe, duration, starts):
    monkeypatch.setattr(_mod.yf, "Ticker", lambda _: _Ticker(_frame(starts)))
    return [item["ts"] for item in _mod.fetch_bars(ticker, timeframe, duration, "1mo")]


def test_일봉은_시작_17시간_뒤부터_담는다(monkeypatch):
    """예전 규칙(시작 + 24시간)은 한국 마감 봉을 다음 날 새벽, 미국 마감 봉을 8시간 뒤에야 담았다."""
    now = datetime.now(timezone.utc)
    closed, in_session = now - timedelta(hours=18), now - timedelta(hours=10)
    got = _fetch(monkeypatch, "AAPL", "1d", timedelta(days=1), [closed, in_session])
    assert got == [closed.isoformat()]


def test_24시간_거래_상품의_일봉은_하루가_다_가야_담는다(monkeypatch):
    now = datetime.now(timezone.utc)
    got = _fetch(monkeypatch, "BTC-USD", "1d", timedelta(days=1), [now - timedelta(hours=30), now - timedelta(hours=18)])
    assert got == [(now - timedelta(hours=30)).isoformat()]


def test_5분봉_규칙은_그대로다(monkeypatch):
    now = datetime.now(timezone.utc)
    got = _fetch(monkeypatch, "AAPL", "5m", timedelta(minutes=5), [now - timedelta(minutes=6), now - timedelta(minutes=2)])
    assert got == [(now - timedelta(minutes=6)).isoformat()]
