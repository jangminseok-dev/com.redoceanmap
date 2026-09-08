import pytest

from stock.adapter.outbound import symbol_resolver
from stock.app.exceptions import MarketDataUnavailableError


async def test_6자리_코드는_그대로():
    assert await symbol_resolver.resolve_symbol("005930") == "005930"


async def test_영문_티커는_대문자로():
    assert await symbol_resolver.resolve_symbol(" aapl ") == "AAPL"


async def test_해외_종목_한국어명은_KRX_조회_없이_별칭으로_해석(monkeypatch):
    def _no_krx():
        raise AssertionError("별칭 히트는 KRX 로드가 없어야 한다")
    monkeypatch.setattr(symbol_resolver, "_load_krx_names", _no_krx)
    assert await symbol_resolver.resolve_symbol("샌디스크") == "SNDK"
    assert await symbol_resolver.resolve_symbol("테슬라") == "TSLA"
    assert await symbol_resolver.resolve_symbol("버크셔 해서웨이") == "BRK-B"  # 공백 제거 매칭


async def test_한국_종목명은_KRX_목록에서_코드로(monkeypatch):
    monkeypatch.setattr(symbol_resolver, "_load_krx_names", lambda: {"삼성전자": "005930"})
    assert await symbol_resolver.resolve_symbol("삼성전자") == "005930"
    assert await symbol_resolver.resolve_symbol("삼성 전자") == "005930"  # 공백 제거 매칭


async def test_부분_일치는_유일할_때만_채택(monkeypatch):
    monkeypatch.setattr(
        symbol_resolver, "_load_krx_names",
        lambda: {"SK하이닉스": "000660", "삼성전자": "005930", "삼성물산": "028260"},
    )
    assert await symbol_resolver.resolve_symbol("하이닉스") == "000660"
    with pytest.raises(MarketDataUnavailableError, match="여러 개"):
        await symbol_resolver.resolve_symbol("삼성")


async def test_미해석_질의는_MarketDataUnavailableError(monkeypatch):
    monkeypatch.setattr(symbol_resolver, "_load_krx_names", lambda: {})
    monkeypatch.setattr(symbol_resolver.yf, "Search", lambda *a, **k: (_ for _ in ()).throw(RuntimeError()))
    with pytest.raises(MarketDataUnavailableError):
        await symbol_resolver.resolve_symbol("없는종목이름123")


@pytest.mark.network
async def test_KRX_실목록_삼성전자():
    assert await symbol_resolver.resolve_symbol("삼성전자") == "005930"


def test_별칭의_정식_명칭_꼬리_변형도_해석한다():
    # 3차 실측 P5: "마이크론 테크놀로지"가 별칭("마이크론") 정확 일치에서 빠져 실패했다
    assert symbol_resolver._resolve_sync("마이크론 테크놀로지") == "MU"
    # 짧은 별칭은 접두 매칭하지 않는다 — "인텔리안테크"(KRX)가 INTC로 오매칭되면 안 된다
    assert "인텔" in symbol_resolver._OVERSEAS_ALIASES


async def test_국내_국민_별칭은_상장명으로_해석한다(monkeypatch):
    # 4차 실측 S5: '네이버'는 상장명이 영문 NAVER라 부분 일치조차 안 걸렸다
    monkeypatch.setattr(
        symbol_resolver, "_load_krx_names",
        lambda: {"NAVER": "035420", "KT": "030200"},
    )
    assert await symbol_resolver.resolve_symbol("네이버") == "035420"
    assert await symbol_resolver.resolve_symbol("케이티") == "030200"


async def test_KRX_목록_조회_실패면_폴백_표로_열화하고_500을_내지_않는다(monkeypatch):
    """2026-09-08 페르소나 QA P04 — FinanceDataReader KRX 404가 '삼성전자' 질문 전체를 500으로 죽였다."""
    calls = []

    def _boom(_):
        calls.append(1)
        raise RuntimeError("HTTP Error 404: Not Found")

    monkeypatch.setattr(symbol_resolver, "_krx_names", None)
    monkeypatch.setattr(symbol_resolver, "_krx_failed_at", None)
    monkeypatch.setattr(symbol_resolver, "_load_from_kind", lambda: (_ for _ in ()).throw(RuntimeError("kind down")))
    monkeypatch.setattr(symbol_resolver.fdr, "StockListing", _boom)

    assert await symbol_resolver.resolve_symbol("삼성전자") == "005930"
    assert await symbol_resolver.resolve_symbol("하이닉스") == "000660"  # 부분 일치도 폴백 표 위에서 동작
    with pytest.raises(MarketDataUnavailableError):
        await symbol_resolver.resolve_symbol("존재하지않는종목")  # 앱 예외(404) — 500 아님
    # 실패는 10분 쿨다운 — 질문마다 KRX를 다시 때리지 않는다
    await symbol_resolver.resolve_symbol("삼성전자")
    assert len(calls) == 1


async def test_KIND_목록이_1순위_소스다(monkeypatch):
    monkeypatch.setattr(symbol_resolver, "_krx_names", None)
    monkeypatch.setattr(symbol_resolver, "_krx_failed_at", None)
    monkeypatch.setattr(symbol_resolver, "_load_from_kind", lambda: {"삼성전자": "005930", "카카오": "035720"})
    monkeypatch.setattr(symbol_resolver.fdr, "StockListing", lambda _: (_ for _ in ()).throw(AssertionError("fdr는 부르지 않는다")))
    assert await symbol_resolver.resolve_symbol("카카오") == "035720"
