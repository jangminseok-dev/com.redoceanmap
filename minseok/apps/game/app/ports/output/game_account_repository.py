from __future__ import annotations

from abc import ABC, abstractmethod

from game.app.dtos.account_dto import Account, ClosedPosition, OpenPosition


class GameAccountRepository(ABC):
    """지갑·포지션·원장을 한 묶음으로 다루는 아웃바운드 포트.

    셋을 따로 쪼개지 않는 이유: 매매 한 번이 **세 테이블을 원자적으로** 바꾼다.
    포트를 나누면 트랜잭션 경계가 유스케이스로 새어나가고, 그 순간 "지갑은 줄었는데 원장은
    안 쓰인" 상태가 만들어질 수 있다(그게 바로 원장으로 잡으려던 버그다).
    """

    @abstractmethod
    async def load(self, user_id: int, epoch_id: int) -> Account | None:
        """현재 시즌 계정. 없으면 None."""
        ...

    @abstractmethod
    async def create(
        self, user_id: int, epoch_id: int, rule_version: str, initial_cash_krw: int, game_day: int
    ) -> Account:
        """초기 자본으로 계정을 만든다. 원장에 `initial` 한 줄이 함께 들어간다."""
        ...

    @abstractmethod
    async def open_position(
        self,
        user_id: int,
        epoch_id: int,
        symbol: str,
        side: str,
        quantity: int,
        entry_tick: int,
        entry_price_krw: int,
        entry_fee_krw: int,
        cash_delta_krw: int,
        game_day: int,
    ) -> OpenPosition:
        """포지션 생성 + 지갑 차감 + 원장 기록을 한 트랜잭션으로."""
        ...

    @abstractmethod
    async def close_position(
        self,
        user_id: int,
        position_id: int,
        closed_tick: int,
        exit_price_krw: int,
        exit_fee_krw: int,
        carry_krw: int,
        realized_pnl_krw: int,
        proceeds_krw: int,
        game_day: int,
    ) -> ClosedPosition:
        """포지션 마감 + 지갑 증가 + 원장 기록을 한 트랜잭션으로."""
        ...

    @abstractmethod
    async def ledger_total(self, user_id: int, epoch_id: int) -> int:
        """원장 합계 — 지갑 잔고와 일치해야 한다(불변식 검증용)."""
        ...
