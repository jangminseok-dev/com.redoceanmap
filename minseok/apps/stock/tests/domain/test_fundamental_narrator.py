from datetime import date

from stock.domain.entities.fundamental_snapshot import FundamentalSnapshot
from stock.domain.services.fundamental_narrator import narrate


def _snap(source="yfinance", **kwargs):
    return FundamentalSnapshot(ticker="TEST", as_of=date(2026, 7, 1), source=source, **kwargs)


def _by_key(insights):
    return {i.key: i for i in insights}


def test_빈_스냅샷이면_빈_리스트():
    assert narrate([]) == []


def test_dart가_yfinance보다_우선한다():
    got = _by_key(narrate([
        _snap(source="yfinance", per=5.0),
        _snap(source="dart", per=40.0),
    ]))
    assert "40.0" in got["per"].text
    assert got["per"].tone == "warning"  # 고평가권


def test_dart에_없는_필드는_yfinance로_보강한다():
    got = _by_key(narrate([
        _snap(source="dart", per=5.0),
        _snap(source="yfinance", roe=0.20),
    ]))
    assert got["per"].tone == "neutral" and "더 오르지 않았어요" in got["per"].text  # 저PER은 긍정색 아님(백테스트 미달)
    assert got["roe"].tone == "positive"


def test_적자_PER은_경고():
    got = _by_key(narrate([_snap(per=-3.0)]))
    assert "적자" in got["per"].text


def test_PBR_1미만은_장부가_이하():
    got = _by_key(narrate([_snap(pbr=0.8)]))
    assert got["pbr"].tone == "neutral"


def test_ROE_15퍼센트_경계는_우수():
    got = _by_key(narrate([_snap(roe=0.15)]))
    assert "15.0%" in got["roe"].text
    assert got["roe"].tone == "positive"


def test_중간값_지표는_문장_생략():
    assert narrate([_snap(per=15.0, pbr=2.0, roe=0.10)]) == []
