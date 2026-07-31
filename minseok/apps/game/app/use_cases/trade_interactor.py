from __future__ import annotations

from game.app.dtos.trade_dto import CloseTradeCommand, OpenTradeCommand, TradeReceipt
from game.app.exceptions import (
    InsufficientCash,
    InvalidOrder,
    PositionNotFound,
    SeasonClosed,
    UnknownSymbol,
)
from game.app.ports.input.trade_use_case import TradeUseCase
from game.app.ports.output.game_account_repository import GameAccountRepository
from game.app.ports.output.game_clock_port import GameClockPort
from game.domain.clock.game_epoch import (
    GAME_EPOCH_ID,
    RULES_VERSION,
    TICKS_PER_GAME_DAY,
    describe,
)
from game.domain.market import price_engine
from game.domain.market.symbol_params import find as find_symbol
from game.domain.trading.trading_rules import (
    INITIAL_CASH_KRW,
    Side,
    close_result,
    entry_cost,
    investable_cash,
)

MAX_QUANTITY_PER_ORDER = 1_000_000  # 정수 오버플로·오타 방어


class TradeInteractor(TradeUseCase):
    """매매 대장 — 체결가는 **요청이 도착한 틱**의 계산값이다.

    지연 체결도, 예약 주문도 없다. 미래 틱을 조회할 수 없으므로(game-harness §1-6)
    "다음 틱에 체결"이라는 개념 자체가 성립하지 않는다.
    """

    def __init__(self, repository: GameAccountRepository, clock: GameClockPort) -> None:
        self._repository = repository
        self._clock = clock

    async def open(self, command: OpenTradeCommand) -> TradeReceipt:
        moment = describe(self._clock.now_tick())
        if moment.season_over:
            raise SeasonClosed("시즌이 종료되어 새로 매매할 수 없습니다")

        if command.quantity <= 0 or command.quantity > MAX_QUANTITY_PER_ORDER:
            raise InvalidOrder("수량은 1주 이상이어야 합니다")
        try:
            side = Side(command.side)
        except ValueError as e:
            raise InvalidOrder("방향은 LONG 또는 SHORT여야 합니다") from e

        params = find_symbol(command.symbol)
        if params is None:
            raise UnknownSymbol(f"게임에 없는 종목입니다: {command.symbol}")

        account = await self._repository.load(command.user_id, GAME_EPOCH_ID)
        if account is None:
            account = await self._repository.create(
                user_id=command.user_id,
                epoch_id=GAME_EPOCH_ID,
                rule_version=RULES_VERSION,
                initial_cash_krw=INITIAL_CASH_KRW,
                game_day=moment.game_day,
            )

        price = price_engine.price_at(params, moment.tick)
        cost = entry_cost(price, command.quantity)
        budget = investable_cash(account.cash_krw)
        if cost.total_krw > budget:
            raise InsufficientCash(
                f"투자 가능 금액을 넘습니다 (필요 {cost.total_krw:,}원 · 가능 {budget:,}원)"
            )

        position = await self._repository.open_position(
            user_id=command.user_id,
            epoch_id=GAME_EPOCH_ID,
            symbol=params.symbol,
            side=side.value,
            quantity=command.quantity,
            entry_tick=moment.tick,
            entry_price_krw=price,
            entry_fee_krw=cost.fee_krw,
            cash_delta_krw=-cost.total_krw,
            game_day=moment.game_day,
        )
        return TradeReceipt(
            position_id=position.id,
            symbol=params.symbol,
            name=params.name,
            side=side.value,
            quantity=command.quantity,
            price_krw=price,
            fee_krw=cost.fee_krw,
            carry_krw=0,
            cash_delta_krw=-cost.total_krw,
            realized_pnl_krw=None,
            cash_krw=account.cash_krw - cost.total_krw,
            tick=moment.tick,
        )

    async def close(self, command: CloseTradeCommand) -> TradeReceipt:
        moment = describe(self._clock.now_tick())
        account = await self._repository.load(command.user_id, GAME_EPOCH_ID)
        if account is None:
            raise PositionNotFound("보유한 포지션이 없습니다")

        position = next(
            (p for p in account.open_positions if p.id == command.position_id), None
        )
        if position is None:
            raise PositionNotFound("포지션을 찾을 수 없거나 이미 청산됐습니다")

        params = find_symbol(position.symbol)
        if params is None:
            raise UnknownSymbol(f"게임에 없는 종목입니다: {position.symbol}")

        # 시즌이 끝난 뒤 청산은 허용한다 — 막으면 마지막 포지션이 영원히 잠긴다.
        # 다만 가격은 시즌 마지막 틱에 멈춘다(price_engine이 클램프).
        price = price_engine.price_at(params, moment.tick)
        held_days = max(0.0, (moment.tick - position.entry_tick) / TICKS_PER_GAME_DAY)
        result = close_result(
            side=Side(position.side),
            entry_price_krw=position.entry_price_krw,
            exit_price_krw=price,
            quantity=position.quantity,
            holding_game_days=held_days,
            entry_fee_krw=position.entry_fee_krw,
        )

        await self._repository.close_position(
            user_id=command.user_id,
            position_id=position.id,
            closed_tick=moment.tick,
            exit_price_krw=price,
            exit_fee_krw=result.fee_krw,
            carry_krw=result.carry_krw,
            realized_pnl_krw=result.realized_pnl_krw,
            proceeds_krw=result.proceeds_krw,
            game_day=moment.game_day,
        )
        return TradeReceipt(
            position_id=position.id,
            symbol=position.symbol,
            name=params.name,
            side=position.side,
            quantity=position.quantity,
            price_krw=price,
            fee_krw=result.fee_krw,
            carry_krw=result.carry_krw,
            cash_delta_krw=result.proceeds_krw,
            realized_pnl_krw=result.realized_pnl_krw,
            cash_krw=account.cash_krw + result.proceeds_krw,
            tick=moment.tick,
        )
