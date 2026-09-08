from __future__ import annotations

from datetime import datetime

from hub.app.dtos.paper_trading_dto import PaperDecisionInfo, PaperOrderInfo, PaperStepOutcome
from hub.app.ports.output.paper_decision_port import PaperDecisionPort
from hub.app.ports.output.paper_trading_port import PaperTradingPort
from stock.app.dtos.paper_dto import StepCommand
from stock.app.ports.input.paper_use_case import PaperUseCase


class PaperTradingGateway(PaperTradingPort):
    """허브 PaperTradingPort 구현 — 유스케이스 step 위임."""

    def __init__(self, use_case: PaperUseCase) -> None:
        self._use_case = use_case

    async def step(self, as_of: datetime, replay: bool) -> PaperStepOutcome:
        r = await self._use_case.step(StepCommand(as_of=as_of, replay=replay))
        return PaperStepOutcome(r.as_of, r.skipped, r.filled, r.decisions, r.scored, r.equity_rows)


class PaperDecisionGateway(PaperDecisionPort):
    """허브 PaperDecisionPort 구현 — chat용 최근 판단(기록 보고 재료)."""

    def __init__(self, use_case: PaperUseCase) -> None:
        self._use_case = use_case

    async def latest(self, accounts: list[str]) -> list[PaperDecisionInfo]:
        out: list[PaperDecisionInfo] = []
        for key in accounts:
            views = await self._use_case.decisions(key, None, None, 1)
            if not views:
                continue
            d = views[0]
            account = await self._use_case.account(key)
            out.append(PaperDecisionInfo(
                account=key, as_of=d.as_of.date(), market_view=d.market_view,
                orders=[PaperOrderInfo(o["ticker"], o["action"], o.get("reason", ""), list(o.get("cites", {}).get("news_ids", [])))
                        for o in d.orders],
                filled_tickers=[t.ticker for t in d.fills],
                equity_krw=account.equity_krw if account else None,
                return_pct=(account.equity_krw / account.initial_cash_krw - 1.0) if account else None,
            ))
        return out
