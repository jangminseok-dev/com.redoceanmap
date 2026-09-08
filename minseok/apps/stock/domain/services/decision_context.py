"""EXAONE 판단 컨텍스트 — 후보 종목·보유 포지션·규칙을 프롬프트 문자열로 조립한다.

순수 함수. **as_of 이전 데이터만** 들어와야 한다는 책임은 호출자(리포지토리 쿼리)에 있고,
이 모듈은 받은 것을 압축해 쓴다. 후보 25종목 상한은 NUM_CTX 8192 안에서 프롬프트가
~3k 토큰에 머물게 하는 장치다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from stock.domain.services import paper_rules as rules

MAX_CANDIDATES = 25
NEWS_PER_CANDIDATE = 2


@dataclass(frozen=True)
class NewsCite:
    news_id: int
    title: str
    sentiment: float | None
    event_type: str | None
    published_on: date


@dataclass(frozen=True)
class Candidate:
    ticker: str
    name: str
    last_close: float
    return_5d_pct: float | None
    direction: str  # UP | DOWN | NEUTRAL | NONE(스냅샷 없음)
    score: float | None
    up_rate: float | None
    baseline_up_rate: float | None
    ready: bool
    atr_pct: float | None
    regime: str | None
    earnings_veto: bool
    sentiment_3d: float | None
    news: tuple[NewsCite, ...] = field(default_factory=tuple)

    @property
    def signal_keys(self) -> tuple[str, ...]:
        return ("snapshot_direction", "up_rate") if self.direction in ("UP", "DOWN") else ()


@dataclass(frozen=True)
class HeldView:
    ticker: str
    side: str
    quantity: int
    avg_price: float
    last_close: float
    unrealized_pct: float
    sessions_held: int


@dataclass(frozen=True)
class DecisionContext:
    as_of: date
    cash_krw: float
    equity_krw: float
    candidates: tuple[Candidate, ...]
    held: tuple[HeldView, ...]

    @property
    def allowed_tickers(self) -> set[str]:
        return {c.ticker for c in self.candidates} | {h.ticker for h in self.held}

    @property
    def allowed_news_ids(self) -> set[int]:
        return {n.news_id for c in self.candidates for n in c.news}


SYSTEM_PROMPT = (
    "당신은 모의투자 포트폴리오 매니저다. 실제 돈이 아니며 매매 권유가 아니라 기록용 판단이다. "
    "제공된 자료만 근거로 삼고, 자료에 없는 사실은 지어내지 않는다. 반드시 JSON 객체 하나만 출력한다."
)


def _pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v * 100:+.1f}%"


def _fmt_candidate(c: Candidate) -> str:
    stats = f"방향={c.direction}"
    if c.score is not None:
        stats += f" score={c.score:+.2f}"
    if c.up_rate is not None:
        stats += f" 과거상승률={c.up_rate:.0%}(기준선 {(c.baseline_up_rate or 0):.0%}, 검증={'예' if c.ready else '아니오'})"
    if c.atr_pct is not None:
        stats += f" ATR={c.atr_pct * 100:.1f}%"
    if c.regime:
        stats += f" 레짐={c.regime}"
    if c.earnings_veto:
        stats += " 실적발표임박"
    if c.sentiment_3d is not None:
        stats += f" 3일감성={c.sentiment_3d:+.2f}"
    lines = [f"- {c.ticker}({c.name}) 종가={c.last_close:g} 5일={_pct(c.return_5d_pct)} {stats}"]
    for n in c.news[:NEWS_PER_CANDIDATE]:
        tag = f"[news_id={n.news_id}]"
        label = f" 감성={n.sentiment:+.2f}" if n.sentiment is not None else ""
        event = f" 유형={n.event_type}" if n.event_type else ""
        lines.append(f"    {tag} {n.published_on:%m/%d} {n.title[:80]}{label}{event}")
    return "\n".join(lines)


def build_prompt(ctx: DecisionContext) -> str:
    held = "\n".join(
        f"- {h.ticker} {h.side} {h.quantity}주 @{h.avg_price:g} 현재 {h.last_close:g} "
        f"({_pct(h.unrealized_pct)}, {h.sessions_held}거래일 보유)"
        for h in ctx.held
    ) or "- 없음"
    candidates = "\n".join(_fmt_candidate(c) for c in ctx.candidates[:MAX_CANDIDATES]) or "- 없음"
    return (
        f"기준일 {ctx.as_of:%Y-%m-%d}. 현금 {ctx.cash_krw:,.0f}원, 총자산 {ctx.equity_krw:,.0f}원.\n"
        f"규칙: 종목당 비중 ≤ {rules.assumed_max_position_weight:.0%}, 동시 보유 ≤ {rules.assumed_max_positions}종목, "
        f"체결은 다음 세션 시가, 수수료 {rules.assumed_fee_rate:.1%}. 숏 가능(레버리지 없음).\n"
        f"판단 근거는 아래 자료뿐이다. 인용은 제시된 news_id와 신호 키(snapshot_direction·up_rate)만 쓴다.\n\n"
        f"## 보유 포지션\n{held}\n\n"
        f"## 후보 종목\n{candidates}\n\n"
        "## 출력 형식(JSON만)\n"
        '{"market_view": "오늘 시장을 보는 한두 문장", "orders": [{"ticker": "AAPL", '
        '"action": "BUY|SELL|SHORT|COVER", "weight": 0.1, "reason": "한 문장", '
        '"cites": {"news_ids": [123], "signals": ["snapshot_direction"]}}]}\n'
        "주문이 없으면 orders를 빈 배열로 둔다. SELL·COVER는 보유 포지션 전량 청산이다."
    )
