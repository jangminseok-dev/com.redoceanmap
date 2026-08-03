"""인메모리 계정 리포지토리 스텁.

mock 프레임워크 대신 스텁 구현을 쓴다(백엔드 컨벤션). 이 스텁이 **원장을 실제로 쌓기 때문에**
불변식(SUM(ledger) == cash)을 유스케이스 테스트에서 그대로 검증할 수 있다 — DB 없이도
"돈이 새는지"를 잡는 것이 목적이다.
"""
from __future__ import annotations

from game.app.dtos.account_dto import Account, ClosedPosition, OpenPosition


class StubAccountRepository:
    def __init__(self) -> None:
        self.wallets: dict[int, dict] = {}
        self.positions: dict[int, dict] = {}
        self.ledger: list[dict] = []
        self._next_id = 1

    # --- 포트 구현 ---------------------------------------------------------

    async def load(self, user_id: int, epoch_id: int) -> Account | None:
        wallet = self.wallets.get(user_id)
        if wallet is None or wallet["epoch_id"] != epoch_id:
            return None
        return Account(
            user_id=user_id,
            cash_krw=wallet["cash_krw"],
            epoch_id=wallet["epoch_id"],
            rule_version=wallet["rule_version"],
            open_positions=tuple(
                OpenPosition(
                    id=p["id"],
                    symbol=p["symbol"],
                    side=p["side"],
                    quantity=p["quantity"],
                    entry_tick=p["entry_tick"],
                    entry_price_krw=p["entry_price_krw"],
                    entry_fee_krw=p["entry_fee_krw"],
                    instrument=p.get("instrument", "STOCK"),
                    leverage=p.get("leverage", 1),
                    expires_tick=p.get("expires_tick"),
                )
                for p in self.positions.values()
                if p["user_id"] == user_id and p["closed_tick"] is None
            ),
        )

    async def create(
        self, user_id: int, epoch_id: int, rule_version: str, initial_cash_krw: int, game_day: int
    ) -> Account:
        self.wallets[user_id] = {
            "cash_krw": initial_cash_krw,
            "epoch_id": epoch_id,
            "rule_version": rule_version,
        }
        self.ledger.append(
            {"user_id": user_id, "source": "initial", "amount_krw": initial_cash_krw}
        )
        return Account(
            user_id=user_id,
            cash_krw=initial_cash_krw,
            epoch_id=epoch_id,
            rule_version=rule_version,
            open_positions=(),
        )

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
        instrument: str = "STOCK",
        leverage: int = 1,
        expires_tick: int | None = None,
    ) -> OpenPosition:
        position_id = self._next_id
        self._next_id += 1
        self.positions[position_id] = {
            "id": position_id,
            "user_id": user_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "entry_tick": entry_tick,
            "entry_price_krw": entry_price_krw,
            "entry_fee_krw": entry_fee_krw,
            "closed_tick": None,
            "instrument": instrument,
            "leverage": leverage,
            "expires_tick": expires_tick,
            "close_reason": None,
            "exit_price_krw": None,
            "realized_pnl_krw": None,
        }
        self.wallets[user_id]["cash_krw"] += cash_delta_krw
        self.ledger.append(
            {"user_id": user_id, "source": "trade", "amount_krw": cash_delta_krw}
        )
        return OpenPosition(
            id=position_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_tick=entry_tick,
            entry_price_krw=entry_price_krw,
            entry_fee_krw=entry_fee_krw,
            instrument=instrument,
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
        position = self.positions[position_id]
        if position["closed_tick"] is not None:
            raise LookupError("이미 청산된 포지션입니다")  # PG의 FOR UPDATE 경로와 같은 계약
        position["closed_tick"] = closed_tick
        position["close_reason"] = close_reason
        position["exit_price_krw"] = exit_price_krw
        position["realized_pnl_krw"] = realized_pnl_krw
        self.wallets[user_id]["cash_krw"] += proceeds_krw
        self.ledger.append(
            {"user_id": user_id, "source": "trade", "amount_krw": proceeds_krw}
        )
        return ClosedPosition(
            id=position_id,
            symbol=position["symbol"],
            side=position["side"],
            quantity=position["quantity"],
            entry_tick=position["entry_tick"],
            entry_price_krw=position["entry_price_krw"],
            closed_tick=closed_tick,
            exit_price_krw=exit_price_krw,
            realized_pnl_krw=realized_pnl_krw,
        )

    async def list_recently_closed(self, user_id, epoch_id, limit: int = 5):
        from game.app.dtos.account_dto import RecentlyClosed
        from game.domain.clock.game_epoch import TICKS_PER_GAME_DAY

        rows = [
            p
            for p in self.positions.values()
            if p["user_id"] == user_id
            and p["closed_tick"] is not None
            and p["close_reason"] not in (None, "user")
        ]
        rows.sort(key=lambda p: p["closed_tick"], reverse=True)
        return tuple(
            RecentlyClosed(
                id=p["id"],
                symbol=p["symbol"],
                name="",
                side=p["side"],
                quantity=p["quantity"],
                leverage=p["leverage"],
                closed_tick=p["closed_tick"],
                closed_game_day=p["closed_tick"] // TICKS_PER_GAME_DAY,
                exit_price_krw=p["exit_price_krw"] or 0,
                realized_pnl_krw=p["realized_pnl_krw"] or 0,
                reason=p["close_reason"],
            )
            for p in rows[:limit]
        )

    async def ledger_total(self, user_id: int, epoch_id: int) -> int:
        return sum(e["amount_krw"] for e in self.ledger if e["user_id"] == user_id)

    # --- 검증 도우미 -------------------------------------------------------

    def assert_invariant(self, user_id: int) -> None:
        """원장 불변식 — 지갑 잔고는 원장 합계와 정확히 같아야 한다."""
        total = sum(e["amount_krw"] for e in self.ledger if e["user_id"] == user_id)
        assert total == self.wallets[user_id]["cash_krw"], (
            f"원장 {total:,} ≠ 지갑 {self.wallets[user_id]['cash_krw']:,}"
        )


class StubClock:
    def __init__(self, tick: int) -> None:
        self.tick = tick

    def now_tick(self) -> int:
        return self.tick
