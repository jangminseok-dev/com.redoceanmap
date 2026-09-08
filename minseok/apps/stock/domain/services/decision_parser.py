"""EXAONE 판단(JSON) 검증 — 허용된 종목·인용·한도만 통과시키고 나머지는 거부 사유와 함께 남긴다.

파서는 "그럴듯한 주문"을 고치지 않는다. 틀리면 거부다 — 화면이 거부 사유까지 보여 주는 것이
이 슬라이스의 정직성 장치다(환각 인용 차단은 chat의 인용 배지와 같은 규칙).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from stock.domain.services import paper_rules as rules


@dataclass(frozen=True)
class Order:
    ticker: str
    action: str  # BUY | SELL | SHORT | COVER
    weight: float  # 진입 비중(0~max) — 청산은 0
    reason: str
    news_ids: tuple[int, ...] = ()
    signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class Rejected:
    ticker: str
    action: str
    reason: str


@dataclass(frozen=True)
class ParsedDecision:
    market_view: str
    orders: tuple[Order, ...]
    rejected: tuple[Rejected, ...] = field(default_factory=tuple)


def reason_kind(order: Order) -> str:
    """이유 유형 — 사후 채점의 집계 축."""
    if order.news_ids and order.signals:
        return "mixed"
    if order.news_ids:
        return "news"
    if order.signals:
        return "indicator"
    return "none"


def _loads(raw: str) -> dict:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("최상위가 객체가 아니다")
    return data


def parse(
    raw: str,
    *,
    allowed_tickers: set[str],
    allowed_news_ids: set[int],
    held_long: set[str],
    held_short: set[str],
) -> ParsedDecision:
    """raw JSON → 주문. 형식 자체가 깨졌으면 ValueError(호출자가 재시도 판단)."""
    data = _loads(raw)
    market_view = str(data.get("market_view", "")).strip()[:500]
    orders: list[Order] = []
    rejected: list[Rejected] = []
    seen: set[tuple[str, str]] = set()

    for item in data.get("orders", []) or []:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker", "")).strip().upper()
        action = str(item.get("action", "")).strip().upper()
        reason = str(item.get("reason", "")).strip()[:300]
        if action not in rules.ACTIONS:
            rejected.append(Rejected(ticker, action, f"지원하지 않는 주문 유형 '{action}' — 매수·매도·숏 진입·숏 청산만 가능하고, 관망은 주문을 내지 않으면 된다"))
            continue
        if ticker not in allowed_tickers:
            rejected.append(Rejected(ticker, action, "후보 목록에 없는 종목"))
            continue
        if (ticker, action) in seen:
            rejected.append(Rejected(ticker, action, "같은 주문이 중복"))
            continue
        if action == "BUY" and ticker in held_short or action == "SHORT" and ticker in held_long:
            rejected.append(Rejected(ticker, action, "반대 포지션 보유 중 — 먼저 청산"))
            continue
        if action == "SELL" and ticker not in held_long:
            rejected.append(Rejected(ticker, action, "보유하지 않은 롱을 매도"))
            continue
        if action == "COVER" and ticker not in held_short:
            rejected.append(Rejected(ticker, action, "보유하지 않은 숏을 커버"))
            continue
        try:
            weight = float(item.get("weight", 0.0) or 0.0)
        except (TypeError, ValueError):
            weight = 0.0
        if action in ("BUY", "SHORT"):
            if weight <= 0:
                rejected.append(Rejected(ticker, action, "진입 비중이 0"))
                continue
            weight = min(weight, rules.assumed_max_position_weight)
        else:
            weight = 0.0
        cites = item.get("cites") or {}
        raw_ids = cites.get("news_ids", []) if isinstance(cites, dict) else []
        news_ids = tuple(
            int(n) for n in raw_ids if isinstance(n, (int, float, str)) and str(n).lstrip("-").isdigit()
            and int(n) in allowed_news_ids
        )
        raw_signals = cites.get("signals", []) if isinstance(cites, dict) else []
        signals = tuple(str(s)[:30] for s in raw_signals if isinstance(s, str))[:6]
        seen.add((ticker, action))
        orders.append(Order(ticker, action, weight, reason, news_ids, signals))

    return ParsedDecision(market_view=market_view, orders=tuple(orders), rejected=tuple(rejected))
