"""일봉 완성 규칙 — 수집과 분석이 같이 쓴다. 예전 "시작 + 24시간"은 마감 봉을 8~13시간 늦게 담았다(2026-09-21)."""
from datetime import UTC, datetime, timedelta

from stock.domain.services.bar_completeness import daily_bar_complete_after, is_daily_bar_complete

US_BAR = datetime(2026, 9, 18, 4, 0, tzinfo=UTC)     # 9/18 뉴욕 자정(서머타임) — 마감은 20:00 UTC
KR_BAR = datetime(2026, 9, 17, 15, 0, tzinfo=UTC)    # 9/18 서울 자정 — 마감은 06:30 UTC


def test_미국_봉은_장_마감_한_시간_뒤에_완성이다():
    assert not is_daily_bar_complete("AAPL", US_BAR, US_BAR + timedelta(hours=16, minutes=30))   # 마감 30분 뒤 — 아직
    assert is_daily_bar_complete("AAPL", US_BAR, US_BAR + timedelta(hours=17))


def test_한국_봉은_평일_16시10분_수집에는_아직이고_17시부터_담긴다():
    assert not is_daily_bar_complete("005930.KS", KR_BAR, KR_BAR + timedelta(hours=16, minutes=10))
    assert is_daily_bar_complete("005930.KS", KR_BAR, KR_BAR + timedelta(hours=17, minutes=5))


def test_장중_봉은_완성이_아니다():
    assert not is_daily_bar_complete("AAPL", US_BAR, US_BAR + timedelta(hours=12))


def test_지수도_같은_규칙이다():
    assert daily_bar_complete_after("^VIX") == daily_bar_complete_after("SPY") == timedelta(hours=17)


def test_24시간_거래_상품은_하루가_다_가야_완성이다():
    for ticker in ("BTC-USD", "ETH-KRW", "KRW=X", "ES=F"):
        assert daily_bar_complete_after(ticker) == timedelta(hours=24)
        assert not is_daily_bar_complete(ticker, US_BAR, US_BAR + timedelta(hours=17))
