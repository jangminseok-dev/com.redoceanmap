from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime

from stock.app.dtos.paper_dto import (
    AccountRecord,
    DecisionDraft,
    DecisionRecord,
    EquityPoint,
    ScoreDraft,
    ScoreRecord,
    TradeDraft,
    TradeRecord,
)
from stock.domain.services.paper_ledger import Position


class PaperAccountRepositoryPort(ABC):
    """모의투자 계정·포지션·원장·판단·평가 영속 포트. 한 트랜잭션이라 한 포트다."""

    @abstractmethod
    async def get_or_create(self, kind: str, user_id: int | None, initial_cash_krw: float,
                            started_on: date) -> AccountRecord: ...

    @abstractmethod
    async def find(self, kind: str, user_id: int | None) -> AccountRecord | None: ...

    @abstractmethod
    async def find_by_id(self, account_id: int) -> AccountRecord | None: ...

    @abstractmethod
    async def list_accounts(self) -> list[AccountRecord]: ...

    @abstractmethod
    async def commit_fill(self, account_id: int, cash_krw: float, positions: list[Position],
                          trade: TradeDraft) -> TradeRecord:
        """체결 1건을 원장에 남기고 현금·포지션을 교체한다(한 트랜잭션)."""
        ...

    @abstractmethod
    async def save_decision(self, draft: DecisionDraft) -> DecisionRecord | None:
        """(account, as_of) 중복이면 None — 재실행 멱등."""
        ...

    @abstractmethod
    async def find_unfilled_decisions(self) -> list[DecisionRecord]: ...

    @abstractmethod
    async def mark_filled(self, decision_id: int, ts: datetime, extra_rejected: list[dict]) -> None: ...

    @abstractmethod
    async def find_unscored_decisions(self, before: datetime) -> list[DecisionRecord]: ...

    @abstractmethod
    async def mark_scored(self, decision_id: int, ts: datetime) -> None: ...

    @abstractmethod
    async def save_scores(self, scores: list[ScoreDraft]) -> int: ...

    @abstractmethod
    async def scores(self, account_id: int) -> list[ScoreRecord]: ...

    @abstractmethod
    async def trades_for_decision(self, decision_id: int) -> list[TradeRecord]: ...

    @abstractmethod
    async def trades(self, account_id: int, limit: int) -> list[TradeRecord]: ...

    @abstractmethod
    async def trade_count(self, account_id: int) -> int: ...

    @abstractmethod
    async def upsert_equity(self, account_id: int, point: EquityPoint) -> bool:
        """신규면 True, 같은 날 행이 있으면 갱신 없이 False."""
        ...

    @abstractmethod
    async def equity_series(self, account_id: int) -> list[EquityPoint]: ...

    @abstractmethod
    async def decisions(self, account_id: int, since: date | None, until: date | None,
                        limit: int) -> list[DecisionRecord]: ...

    @abstractmethod
    async def decision_by_id(self, decision_id: int) -> DecisionRecord | None: ...
