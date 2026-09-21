"""일봉이 완성됐는가 — 수집(scripts/collect_prices.py)과 분석(StockInteractor)이 같은 규칙을 쓴다(순수, 표준 라이브러리만).

일봉의 ts는 그 거래일의 **시작**(거래소 현지 자정)이다. 봉은 장 마감 때 완성되는데 수집은 "시작 + 24시간"이 지나야 완성으로 봤다 —
한국 봉은 마감(15:30) 13시간 반 뒤인 다음 날 05시, 미국 봉은 마감(05:00 KST) 8시간 뒤인 13시에야 DB에 들어왔다(2026-09-21 실측).
평일 16:10의 "마감 봉 반영" cron이 있었지만 이 규칙 때문에 그 시각엔 절대 담지 못했다.

시작 + 17시간이면 수집 대상 시장(미국 16:00 · 한국 15:30 · 수능일 16:30 · VIX 15:15 현지 마감)이 전부 닫힌 뒤이고 1시간 안팎의 여유가 남는다 —
수집은 한번 저장한 봉을 갱신하지 않으므로(DO NOTHING) 마감 직후의 미확정 값을 담지 않기 위한 여유다. ts 기준 상대 시간이라 서머타임과 무관하다.
24시간 거래 상품(암호화폐·외환·선물)은 하루가 다 가야 완성이다 — 지금 수집 대상엔 없지만 들어오면 조용히 틀리지 않게 예외로 둔다.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

SESSION_MARKET_COMPLETE_AFTER = timedelta(hours=17)
ROUND_THE_CLOCK_COMPLETE_AFTER = timedelta(hours=24)
_ROUND_THE_CLOCK = re.compile(r"(-USD|-KRW|=X|=F)$", re.IGNORECASE)   # 야후 표기: 암호화폐 · 외환 · 선물


def daily_bar_complete_after(ticker: str) -> timedelta:
    return ROUND_THE_CLOCK_COMPLETE_AFTER if _ROUND_THE_CLOCK.search(ticker) else SESSION_MARKET_COMPLETE_AFTER


def is_daily_bar_complete(ticker: str, bar_start: datetime, now: datetime) -> bool:
    """bar_start·now는 시간대가 있는 시각(같은 기준으로 비교된다)."""
    return bar_start + daily_bar_complete_after(ticker) <= now
