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
from game.app.ports.output.game_intervention_repository import GameInterventionRepository
from game.app.use_cases.active_interventions import load_active
from game.domain.clock.game_epoch import (
    GAME_EPOCH_ID,
    RULES_VERSION,
    TICKS_PER_GAME_DAY,
    describe,
)
from game.domain.market import orderbook, price_engine
from game.domain.market.symbol_params import find as find_symbol
from game.domain.trading.liquidation import resolve_close
from game.domain.trading.trading_rules import (
    INITIAL_CASH_KRW,
    LEVERAGE_TIERS,
    LEVERAGED_EXPIRY_TICKS,
    MAX_LEVERAGED_POSITIONS,
    Side,
    close_result,
    entry_cost,
    investable_cash,
    liquidation_price,
)

MAX_QUANTITY_PER_ORDER = 1_000_000  # 정수 오버플로·오타 방어


class TradeInteractor(TradeUseCase):
    """매매 대장 — 체결가는 **요청이 도착한 틱**의 계산값이다.

    지연 체결도, 예약 주문도 없다. 미래 틱을 조회할 수 없으므로(game-harness §1-6)
    "다음 틱에 체결"이라는 개념 자체가 성립하지 않는다.
    """

    def __init__(
        self,
        repository: GameAccountRepository,
        clock: GameClockPort,
        interventions: GameInterventionRepository | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._interventions = interventions

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
        if command.leverage not in LEVERAGE_TIERS:
            raise InvalidOrder(
                f"레버리지는 {'·'.join(str(t) for t in LEVERAGE_TIERS)}배 중 하나여야 합니다"
            )

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

        # 레버리지 포지션은 스캔 비용이 있다 — 동시 보유를 제한해 지갑 조회 상한을 지킨다
        if command.leverage > 1:
            open_leveraged = sum(1 for p in account.open_positions if p.leverage > 1)
            if open_leveraged >= MAX_LEVERAGED_POSITIONS:
                raise InvalidOrder(
                    f"레버리지 포지션은 동시에 {MAX_LEVERAGED_POSITIONS}개까지만 보유할 수 있습니다"
                )

        extra = await load_active(self._interventions, moment.tick)
        price = price_engine.price_at(params, moment.tick, None, extra)
        _guard_halt(params, moment.tick, price, extra)
        # **호가를 걷어올리며 체결된다.** 현재가에 전량 체결하면 "10억을 한 번에 사도
        # 현재가"라는 비현실이 남는다 — 유동성 비용이 슬리피지로 드러나야 한다.
        filled = _market_fill(params, moment.tick, price, side.value, command.quantity, extra)
        price = filled.avg_price_krw
        cost = entry_cost(price, command.quantity, command.leverage)
        budget = investable_cash(account.cash_krw)
        if cost.total_krw > budget:
            raise InsufficientCash(
                f"투자 가능 금액을 넘습니다 (필요 {cost.total_krw:,}원 · 가능 {budget:,}원)"
            )

        # 만료는 레버리지에만 붙는다 — 이게 청산 스캔 범위를 유한하게 만든다
        expires_tick = (
            moment.tick + LEVERAGED_EXPIRY_TICKS if command.leverage > 1 else None
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
            leverage=command.leverage,
            expires_tick=expires_tick,
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
            leverage=command.leverage,
            liquidation_price_krw=liquidation_price(side, price, command.leverage),
            expires_tick=expires_tick,
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

        extra = await load_active(self._interventions, moment.tick)
        _guard_halt(params, moment.tick, price_engine.price_at(params, moment.tick, None, extra), extra)

        # **이미 청산됐어야 하는 포지션인지 먼저 본다.** 지갑을 거치지 않고 바로 청산 버튼을
        # 누르면 미접속 중 터진 포지션을 현재가로 닫게 되어 결정론이 깨진다 — 같은 상황을
        # 두 경로가 다르게 판정하면 안 된다.
        hit = resolve_close(
            lambda tick: price_engine.price_at(params, tick, None, extra),
            side=Side(position.side),
            entry_price_krw=position.entry_price_krw,
            leverage=position.leverage,
            entry_tick=position.entry_tick,
            now_tick=moment.tick,
            expires_tick=position.expires_tick,
        )
        # 시즌이 끝난 뒤 청산은 허용한다 — 막으면 마지막 포지션이 영원히 잠긴다.
        # 다만 가격은 시즌 마지막 틱에 멈춘다(price_engine이 클램프).
        closed_tick = hit.tick if hit else moment.tick
        if hit:
            # 강제청산·만료는 그 시점 가격으로 이미 확정됐다 — 호가를 다시 태우지 않는다
            price = hit.price_krw
        else:
            spot = price_engine.price_at(params, moment.tick, None, extra)
            # 청산은 진입의 반대 방향으로 호가를 소진한다
            exit_side = "SHORT" if position.side == "LONG" else "LONG"
            price = _market_fill(
                params, moment.tick, spot, exit_side, position.quantity, extra
            ).avg_price_krw
        held_days = max(0.0, (closed_tick - position.entry_tick) / TICKS_PER_GAME_DAY)
        result = close_result(
            side=Side(position.side),
            entry_price_krw=position.entry_price_krw,
            exit_price_krw=price,
            quantity=position.quantity,
            holding_game_days=held_days,
            entry_fee_krw=position.entry_fee_krw,
            leverage=position.leverage,
            forced=hit.forced if hit else False,
        )

        await self._repository.close_position(
            user_id=command.user_id,
            position_id=position.id,
            closed_tick=closed_tick,
            exit_price_krw=price,
            exit_fee_krw=result.fee_krw,
            carry_krw=result.carry_krw,
            realized_pnl_krw=result.realized_pnl_krw,
            proceeds_krw=result.proceeds_krw,
            game_day=closed_tick // TICKS_PER_GAME_DAY,
            close_reason=hit.reason if hit else "user",
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


def _market_fill(
    params,
    tick: int,
    spot_krw: int,
    side: str,
    quantity: int,
    extra,
):
    """시장가 체결가. 호가창을 만들어 걷어올린다."""
    candles = price_engine.daily_candles(params, tick, 1, extra)
    volume = candles[-1].simulated_volume if candles else 1
    book = orderbook.build(
        params, spot_krw, tick, volume, price_engine.tick_size(spot_krw)
    )
    return orderbook.fill(book, side, quantity, spot_krw)


def _guard_halt(params, tick: int, price_krw: int, extra) -> None:
    """변동성 완화 장치(VI)가 걸려 있으면 주문을 막는다.

    실제 거래소가 급변 구간에 매매를 멈추는 장치이고, 게임에서는 "폭등하는 순간 다 사버리는"
    경로를 끊는다.
    """
    day_start = (tick // TICKS_PER_GAME_DAY) * TICKS_PER_GAME_DAY
    day_open = price_engine._day_open(params, day_start, tuple(extra))
    if orderbook.vi_triggered(day_open, price_krw):
        raise InvalidOrder(
            f"변동성 완화장치(VI)가 발동해 잠시 매매할 수 없습니다 "
            f"(시가 대비 {abs(price_krw - day_open) / day_open * 100:.1f}% 변동)"
        )
