from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from game.adapter.outbound.orm.game_ledger_orm import GameLedgerOrm
from game.adapter.outbound.orm.game_position_orm import GamePositionOrm
from game.adapter.outbound.orm.game_wallet_orm import GameWalletOrm
from game.app.dtos.account_dto import Account, ClosedPosition, OpenPosition, RecentlyClosed
from game.app.ports.output.game_account_repository import GameAccountRepository
from game.domain.clock.game_epoch import TICKS_PER_GAME_DAY


class GameAccountPgRepository(GameAccountRepository):
    """지갑·포지션·원장 영속.

    쓰기 메서드는 전부 **커밋 한 번**으로 끝난다 — 세 테이블이 따로 커밋되면
    "지갑은 줄었는데 원장은 안 쓰인" 상태가 생기고, 그게 바로 원장으로 잡으려던 버그다.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load(self, user_id: int, epoch_id: int) -> Account | None:
        wallet = await self._session.scalar(
            select(GameWalletOrm).where(
                GameWalletOrm.user_id == user_id, GameWalletOrm.epoch_id == epoch_id
            )
        )
        if wallet is None:
            return None

        rows = await self._session.scalars(
            select(GamePositionOrm)
            .where(
                GamePositionOrm.user_id == user_id,
                GamePositionOrm.epoch_id == epoch_id,
                GamePositionOrm.closed_tick.is_(None),
            )
            .order_by(GamePositionOrm.id)
        )
        return Account(
            user_id=wallet.user_id,
            cash_krw=wallet.cash_krw,
            epoch_id=wallet.epoch_id,
            rule_version=wallet.rule_version,
            open_positions=tuple(
                OpenPosition(
                    id=r.id,
                    symbol=r.symbol,
                    side=r.side,
                    quantity=r.quantity,
                    entry_tick=r.entry_tick,
                    entry_price_krw=r.entry_price_krw,
                    entry_fee_krw=r.entry_fee_krw,
                    leverage=r.leverage,
                    expires_tick=r.expires_tick,
                )
                for r in rows
            ),
        )

    async def create(
        self, user_id: int, epoch_id: int, rule_version: str, initial_cash_krw: int, game_day: int
    ) -> Account:
        wallet = GameWalletOrm(
            user_id=user_id,
            cash_krw=initial_cash_krw,
            epoch_id=epoch_id,
            rule_version=rule_version,
        )
        self._session.add(wallet)
        self._session.add(
            GameLedgerOrm(
                user_id=user_id,
                game_day=game_day,
                source="initial",
                amount_krw=initial_cash_krw,
                ref_type=None,
                ref_id=None,
                epoch_id=epoch_id,
            )
        )
        await self._session.commit()
        return Account(
            user_id=user_id,
            cash_krw=initial_cash_krw,
            epoch_id=epoch_id,
            rule_version=rule_version,
            open_positions=(),
        )

    async def adjust_cash(
        self,
        user_id: int,
        epoch_id: int,
        amount_krw: int,
        game_day: int,
        source: str,
        ref_type: str | None = None,
        ref_id: int | None = None,
    ) -> int:
        wallet = await self._session.scalar(
            select(GameWalletOrm).where(
                GameWalletOrm.user_id == user_id, GameWalletOrm.epoch_id == epoch_id
            )
        )
        if wallet is None:
            raise ValueError("현재 시즌 지갑이 없습니다")
        if wallet.cash_krw + amount_krw < 0:
            raise ValueError(
                f"잔고가 음수가 됩니다 (현재 {wallet.cash_krw:,}원 · 요청 {amount_krw:,}원)"
            )
        wallet.cash_krw += amount_krw
        self._session.add(
            GameLedgerOrm(
                user_id=user_id,
                game_day=game_day,
                source=source,
                amount_krw=amount_krw,
                ref_type=ref_type,
                ref_id=ref_id,
                epoch_id=epoch_id,
            )
        )
        await self._session.commit()
        return wallet.cash_krw

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
        leverage: int = 1,
        expires_tick: int | None = None,
    ) -> OpenPosition:
        wallet = await self._locked_wallet(user_id, epoch_id)
        position = GamePositionOrm(
            user_id=user_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_tick=entry_tick,
            entry_price_krw=entry_price_krw,
            entry_fee_krw=entry_fee_krw,
            leverage=leverage,
            expires_tick=expires_tick,
            epoch_id=epoch_id,
        )
        self._session.add(position)
        await self._session.flush()  # position.id 확보 — 원장이 참조한다

        wallet.cash_krw += cash_delta_krw
        self._session.add(
            GameLedgerOrm(
                user_id=user_id,
                game_day=game_day,
                source="trade",
                amount_krw=cash_delta_krw,
                ref_type="position",
                ref_id=position.id,
                epoch_id=epoch_id,
            )
        )
        await self._session.commit()
        return OpenPosition(
            id=position.id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_tick=entry_tick,
            entry_price_krw=entry_price_krw,
            entry_fee_krw=entry_fee_krw,
            leverage=leverage,
            expires_tick=expires_tick,
        )

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
        close_reason: str = "user",
    ) -> ClosedPosition:
        position = await self._session.scalar(
            select(GamePositionOrm)
            .where(
                GamePositionOrm.id == position_id,
                GamePositionOrm.user_id == user_id,  # 남의 포지션 청산 차단
                GamePositionOrm.closed_tick.is_(None),
            )
            .with_for_update()
        )
        if position is None:
            raise LookupError("포지션이 없거나 이미 청산됐습니다")

        wallet = await self._locked_wallet(user_id, position.epoch_id)
        position.closed_tick = closed_tick
        position.exit_price_krw = exit_price_krw
        position.exit_fee_krw = exit_fee_krw
        position.carry_krw = carry_krw
        position.realized_pnl_krw = realized_pnl_krw
        position.close_reason = close_reason

        wallet.cash_krw += proceeds_krw
        self._session.add(
            GameLedgerOrm(
                user_id=user_id,
                game_day=game_day,
                source="trade",
                amount_krw=proceeds_krw,
                ref_type="position",
                ref_id=position.id,
                epoch_id=position.epoch_id,
            )
        )
        await self._session.commit()
        return ClosedPosition(
            id=position.id,
            symbol=position.symbol,
            side=position.side,
            quantity=position.quantity,
            entry_tick=position.entry_tick,
            entry_price_krw=position.entry_price_krw,
            closed_tick=closed_tick,
            exit_price_krw=exit_price_krw,
            realized_pnl_krw=realized_pnl_krw,
        )

    async def list_recently_closed(
        self, user_id: int, epoch_id: int, limit: int = 5
    ) -> tuple[RecentlyClosed, ...]:
        rows = (
            await self._session.scalars(
                select(GamePositionOrm)
                .where(
                    GamePositionOrm.user_id == user_id,
                    GamePositionOrm.epoch_id == epoch_id,
                    GamePositionOrm.closed_tick.is_not(None),
                    # 유저가 직접 누른 청산은 이미 화면에서 결과를 봤다
                    GamePositionOrm.close_reason.is_not(None),
                    GamePositionOrm.close_reason != "user",
                )
                .order_by(GamePositionOrm.closed_tick.desc())
                .limit(limit)
            )
        ).all()
        return tuple(
            RecentlyClosed(
                id=r.id,
                symbol=r.symbol,
                name="",  # 종목명은 도메인 파라미터라 유스케이스가 채운다
                side=r.side,
                quantity=r.quantity,
                leverage=r.leverage,
                closed_tick=r.closed_tick or 0,
                closed_game_day=(r.closed_tick or 0) // TICKS_PER_GAME_DAY,
                exit_price_krw=r.exit_price_krw or 0,
                realized_pnl_krw=r.realized_pnl_krw or 0,
                reason=r.close_reason or "",
            )
            for r in rows
        )

    async def ledger_total(self, user_id: int, epoch_id: int) -> int:
        total = await self._session.scalar(
            select(func.coalesce(func.sum(GameLedgerOrm.amount_krw), 0)).where(
                GameLedgerOrm.user_id == user_id, GameLedgerOrm.epoch_id == epoch_id
            )
        )
        return int(total or 0)

    async def _locked_wallet(self, user_id: int, epoch_id: int) -> GameWalletOrm:
        """잔고 갱신 전 행 잠금 — 같은 유저의 동시 주문이 잔고를 덮어쓰지 않게."""
        wallet = await self._session.scalar(
            select(GameWalletOrm)
            .where(GameWalletOrm.user_id == user_id, GameWalletOrm.epoch_id == epoch_id)
            .with_for_update()
        )
        if wallet is None:
            raise LookupError("지갑이 없습니다")
        return wallet
