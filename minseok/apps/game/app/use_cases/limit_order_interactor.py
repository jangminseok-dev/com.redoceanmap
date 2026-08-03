from __future__ import annotations

from game.app.dtos.limit_order_dto import (
    LimitOrderView,
    OrderActionCommand,
    OrderListQuery,
    OrderListResponse,
    OrderReceipt,
    PlaceEntryOrderCommand,
    PlaceExitOrderCommand,
)
from game.app.exceptions import (
    InsufficientCash,
    InvalidOrder,
    PositionNotFound,
    SeasonClosed,
    UnknownSymbol,
)
from game.app.ports.input.limit_order_use_case import LimitOrderUseCase
from game.app.ports.output.game_account_repository import GameAccountRepository
from game.app.ports.output.game_clock_port import GameClockPort
from game.app.ports.output.game_intervention_repository import GameInterventionRepository
from game.app.ports.output.game_limit_order_repository import (
    GameLimitOrderRepository,
    LimitOrderRecord,
)
from game.app.use_cases.active_interventions import load_active
from game.domain.clock.game_epoch import (
    GAME_EPOCH_ID,
    RULES_VERSION,
    TICKS_PER_GAME_DAY,
    describe,
)
from game.domain.market import fundamentals, orderbook, price_engine
from game.domain.market.symbol_params import find as find_symbol
from game.domain.trading.limit_fill import is_expired, resolve_fill
from game.domain.trading.liquidation import resolve_close
from game.domain.trading.trading_rules import (
    INITIAL_CASH_KRW,
    LEVERAGE_TIERS,
    LIMIT_ORDER_EXPIRY_TICKS,
    MAX_PENDING_LIMIT_ORDERS,
    Side,
    close_result,
    entry_cost,
    investable_cash,
)

MAX_QUANTITY_PER_ORDER = 1_000_000  # 시장가 주문과 같은 상한


class LimitOrderInteractor(LimitOrderUseCase):
    """지정가 주문 대장 — 접수·취소·연장, 그리고 **조회 시점의 체결 판정**.

    cron이 없으므로 "지금 체결됐는가"는 항상 사후에 답한다(game-strategy §7-12).
    모든 진입점이 `_settle`을 먼저 돌리고, `_settle`은 멱등이다.

    **강제청산이 지정가보다 우선한다.** 같은 구간에서 청산 조건이 먼저(또는 같은 틱에)
    걸렸으면 그 포지션은 이미 사라진 것으로 보고 걸려 있던 청산 예약을 취소한다 —
    증거금 규칙이 상한이고 예약은 편의라서, 반대로 두면 규칙이 예약으로 무력화된다.
    """

    def __init__(
        self,
        orders: GameLimitOrderRepository,
        repository: GameAccountRepository,
        clock: GameClockPort,
        interventions: GameInterventionRepository | None = None,
    ) -> None:
        self._orders = orders
        self._repository = repository
        self._clock = clock
        self._interventions = interventions

    # ── 접수 ────────────────────────────────────────────────────────────────

    async def place_entry(self, command: PlaceEntryOrderCommand) -> OrderReceipt:
        moment = describe(self._clock.now_tick())
        if moment.season_over:
            raise SeasonClosed("시즌이 종료되어 새로 예약할 수 없습니다")
        if command.quantity <= 0 or command.quantity > MAX_QUANTITY_PER_ORDER:
            raise InvalidOrder("수량은 1주 이상이어야 합니다")
        if command.limit_price_krw <= 0:
            raise InvalidOrder("지정가는 1원 이상이어야 합니다")
        if command.leverage not in LEVERAGE_TIERS:
            raise InvalidOrder(
                f"레버리지는 {'·'.join(str(t) for t in LEVERAGE_TIERS)}배 중 하나여야 합니다"
            )
        try:
            side = Side(command.side)
        except ValueError as e:
            raise InvalidOrder("방향은 LONG 또는 SHORT여야 합니다") from e

        params = find_symbol(command.symbol)
        if params is None:
            raise UnknownSymbol(f"게임에 없는 종목입니다: {command.symbol}")

        account = await self._ensure_account(command.user_id, moment.game_day)
        await self._settle(command.user_id, moment.tick, moment.game_day)
        await self._guard_pending_limit(command.user_id)

        extra = await load_active(self._interventions, moment.tick)
        spot = price_engine.price_at(params, moment.tick, None, extra)
        # 부분체결이 없으므로 **접수 시점에** 호가 잔량을 넘는 수량을 거부한다.
        # 대기시켰다가 체결 순간 실패시키면 유저가 이유를 알 방법이 없다.
        self._guard_book_capacity(params, moment.tick, spot, side.value, command.quantity, extra)

        cost = entry_cost(command.limit_price_krw, command.quantity, command.leverage)
        budget = investable_cash(account.cash_krw)
        if cost.total_krw > budget:
            raise InsufficientCash(
                f"투자 가능 금액을 넘습니다 (필요 {cost.total_krw:,}원 · 가능 {budget:,}원)"
            )

        order = await self._orders.place(
            user_id=command.user_id,
            epoch_id=GAME_EPOCH_ID,
            kind="ENTRY",
            symbol=params.symbol,
            side=side.value,
            # 롱은 내려오면 사고, 숏은 올라가면 판다
            trigger="le" if side is Side.LONG else "ge",
            limit_price_krw=command.limit_price_krw,
            quantity=command.quantity,
            placed_tick=moment.tick,
            expires_tick=moment.tick + LIMIT_ORDER_EXPIRY_TICKS,
            leverage=command.leverage,
            reserved_cash_krw=cost.total_krw,
        )
        # 예약금을 지금 묶는다 — 안 묶으면 체결 판정 때 잔액이 모자라 조용히 실패한다.
        cash = await self._repository.adjust_cash(
            user_id=command.user_id,
            epoch_id=GAME_EPOCH_ID,
            amount_krw=-cost.total_krw,
            game_day=moment.game_day,
            source="limit_reserve",
            ref_type="limit_order",
            ref_id=order.id,
        )
        return OrderReceipt(orders=(self._to_view(order),), cash_krw=cash)

    async def place_exit(self, command: PlaceExitOrderCommand) -> OrderReceipt:
        moment = describe(self._clock.now_tick())
        if command.take_profit_krw is None and command.stop_loss_krw is None:
            raise InvalidOrder("익절가나 손절가 중 하나는 있어야 합니다")

        await self._settle(command.user_id, moment.tick, moment.game_day)
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

        # 이미 걸린 예약은 갈아끼운다 — 같은 포지션에 익절이 2개 쌓이면 중복 청산이 된다.
        await self._orders.cancel_for_position(position.id)
        await self._guard_pending_limit(command.user_id)

        long_side = position.side == Side.LONG.value
        placed = []
        expires = moment.tick + LIMIT_ORDER_EXPIRY_TICKS
        for price, is_take in ((command.take_profit_krw, True), (command.stop_loss_krw, False)):
            if price is None:
                continue
            if price <= 0:
                raise InvalidOrder("가격은 1원 이상이어야 합니다")
            # 롱은 오르면 익절·내리면 손절, 숏은 그 반대다.
            trigger = "ge" if long_side == is_take else "le"
            placed.append(
                await self._orders.place(
                    user_id=command.user_id,
                    epoch_id=GAME_EPOCH_ID,
                    kind="EXIT",
                    symbol=position.symbol,
                    side=position.side,
                    trigger=trigger,
                    limit_price_krw=price,
                    quantity=position.quantity,
                    placed_tick=moment.tick,
                    expires_tick=expires,
                    leverage=position.leverage,
                    position_id=position.id,
                )
            )
        return OrderReceipt(
            orders=tuple(self._to_view(o) for o in placed), cash_krw=account.cash_krw
        )

    # ── 취소 · 연장 ─────────────────────────────────────────────────────────

    async def cancel(self, command: OrderActionCommand) -> OrderReceipt:
        moment = describe(self._clock.now_tick())
        await self._settle(command.user_id, moment.tick, moment.game_day)

        order = await self._orders.find(command.user_id, command.order_id)
        if order is None:
            raise InvalidOrder("주문을 찾을 수 없습니다")
        if order.status != "pending":
            raise InvalidOrder("이미 종료된 주문입니다")

        await self._orders.mark_closed(order.id, "cancelled")
        cash = await self._release_reserve(order, moment.game_day)
        return OrderReceipt(orders=(self._to_view(order, status="cancelled"),), cash_krw=cash)

    async def extend(self, command: OrderActionCommand) -> OrderReceipt:
        moment = describe(self._clock.now_tick())
        await self._settle(command.user_id, moment.tick, moment.game_day)

        order = await self._orders.find(command.user_id, command.order_id)
        if order is None:
            raise InvalidOrder("주문을 찾을 수 없습니다")
        if order.status != "pending":
            raise InvalidOrder("이미 종료된 주문입니다")

        # 지금부터 다시 세는 게 아니라 **연장 시점 기준**으로 상한을 다시 준다.
        extended = moment.tick + LIMIT_ORDER_EXPIRY_TICKS
        await self._orders.extend(order.id, extended)
        account = await self._repository.load(command.user_id, GAME_EPOCH_ID)
        return OrderReceipt(
            orders=(self._to_view(order, expires_tick=extended),),
            cash_krw=account.cash_krw if account else 0,
        )

    # ── 조회 (= 체결 판정) ──────────────────────────────────────────────────

    async def list_orders(self, query: OrderListQuery) -> OrderListResponse:
        moment = describe(self._clock.now_tick())
        settled = await self._settle(query.user_id, moment.tick, moment.game_day)
        pending = await self._orders.list_pending(query.user_id, GAME_EPOCH_ID)
        recent = await self._orders.list_recent(query.user_id, GAME_EPOCH_ID)
        return OrderListResponse(
            tick=moment.tick,
            pending=tuple(self._to_view(o) for o in pending),
            recent=tuple(self._to_view(o) for o in recent),
            settled_count=settled,
        )

    # ── 내부 ────────────────────────────────────────────────────────────────

    async def _settle(self, user_id: int, now_tick: int, game_day: int) -> int:
        """밀린 주문을 확정한다. 멱등 — 두 번 돌려도 같은 상태가 된다."""
        pending = await self._orders.list_pending(user_id, GAME_EPOCH_ID)
        if not pending:
            return 0

        extra = await load_active(self._interventions, now_tick)
        account = await self._repository.load(user_id, GAME_EPOCH_ID)
        open_ids = {p.id: p for p in account.open_positions} if account else {}

        settled = 0
        for order in pending:
            params = find_symbol(order.symbol)
            if params is None:  # 시즌이 바뀌어 사라진 종목 — 묶인 돈을 돌려주고 닫는다
                await self._orders.mark_closed(order.id, "cancelled")
                await self._release_reserve(order, game_day)
                settled += 1
                continue

            def price_of(tick: int, p=params) -> int:
                return price_engine.price_at(p, tick, None, extra)

            hit = resolve_fill(
                price_of,
                trigger=order.trigger,
                limit_price_krw=order.limit_price_krw,
                placed_tick=order.placed_tick,
                now_tick=now_tick,
                expires_tick=order.expires_tick,
            )

            if order.kind == "EXIT":
                position = open_ids.get(order.position_id or -1)
                if position is None:  # 이미 닫힌 포지션에 남은 예약
                    await self._orders.mark_closed(order.id, "cancelled")
                    settled += 1
                    continue
                # 강제청산 우선 — 청산이 먼저면(같은 틱 포함) 예약은 무효다.
                forced = resolve_close(
                    price_of,
                    side=Side(position.side),
                    entry_price_krw=position.entry_price_krw,
                    leverage=position.leverage,
                    entry_tick=position.entry_tick,
                    now_tick=now_tick,
                    expires_tick=position.expires_tick,
                )
                if forced and (hit is None or forced.tick <= hit.tick):
                    await self._orders.mark_closed(order.id, "cancelled")
                    settled += 1
                    continue
                if hit:
                    await self._fill_exit(user_id, order, position, params, hit)
                    settled += 1
                    continue
            elif hit:
                await self._fill_entry(user_id, order, params, hit, game_day)
                settled += 1
                continue

            if is_expired(now_tick, order.expires_tick):
                await self._orders.mark_closed(order.id, "expired")
                await self._release_reserve(order, game_day)
                settled += 1
        return settled

    async def _fill_entry(
        self, user_id: int, order: LimitOrderRecord, params, hit, game_day: int
    ) -> None:
        cost = entry_cost(order.limit_price_krw, order.quantity, order.leverage)
        # 묶어둔 돈을 풀고 실제 비용으로 다시 뺀다 — 원장에 두 줄이 남아 추적 가능하다.
        await self._release_reserve(order, game_day)
        await self._repository.open_position(
            user_id=user_id,
            epoch_id=GAME_EPOCH_ID,
            symbol=params.symbol,
            side=order.side,
            quantity=order.quantity,
            entry_tick=hit.tick,
            entry_price_krw=hit.price_krw,
            entry_fee_krw=cost.fee_krw,
            cash_delta_krw=-cost.total_krw,
            game_day=hit.tick // TICKS_PER_GAME_DAY,
            leverage=order.leverage,
            expires_tick=(
                hit.tick + LIMIT_ORDER_EXPIRY_TICKS if order.leverage > 1 else None
            ),
        )
        await self._orders.mark_filled(order.id, hit.tick, hit.price_krw)

    async def _fill_exit(
        self, user_id: int, order: LimitOrderRecord, position, params, hit
    ) -> None:
        held_days = max(0.0, (hit.tick - position.entry_tick) / TICKS_PER_GAME_DAY)
        result = close_result(
            side=Side(position.side),
            entry_price_krw=position.entry_price_krw,
            exit_price_krw=hit.price_krw,
            quantity=position.quantity,
            holding_game_days=held_days,
            entry_fee_krw=position.entry_fee_krw,
            leverage=position.leverage,
            forced=False,  # 예약 체결은 자발 청산이다 — 강제청산 수수료를 물리지 않는다
            dividend_per_share_krw=fundamentals.dividends_between(
                params, position.entry_tick, hit.tick
            ),
        )
        try:
            await self._repository.close_position(
                user_id=user_id,
                position_id=position.id,
                closed_tick=hit.tick,
                exit_price_krw=hit.price_krw,
                exit_fee_krw=result.fee_krw,
                carry_krw=result.carry_krw,
                realized_pnl_krw=result.realized_pnl_krw,
                proceeds_krw=result.proceeds_krw,
                game_day=hit.tick // TICKS_PER_GAME_DAY,
                close_reason="limit",
            )
        except LookupError:
            # 다른 경로(지갑 조회의 지연 마감)가 먼저 닫았다 — 예약만 정리한다.
            await self._orders.mark_closed(order.id, "cancelled")
            return
        await self._orders.mark_filled(order.id, hit.tick, hit.price_krw)
        # OCO — 같은 포지션의 나머지 예약을 취소한다.
        await self._orders.cancel_for_position(position.id, except_order_id=order.id)

    async def _release_reserve(self, order: LimitOrderRecord, game_day: int) -> int:
        """묶어둔 예약금을 지갑으로 돌려준다. 청산 예약은 묶은 돈이 없다."""
        account = await self._repository.load(order.user_id, GAME_EPOCH_ID)
        if order.reserved_cash_krw <= 0:
            return account.cash_krw if account else 0
        return await self._repository.adjust_cash(
            user_id=order.user_id,
            epoch_id=GAME_EPOCH_ID,
            amount_krw=order.reserved_cash_krw,
            game_day=game_day,
            source="limit_release",
            ref_type="limit_order",
            ref_id=order.id,
        )

    async def _ensure_account(self, user_id: int, game_day: int):
        account = await self._repository.load(user_id, GAME_EPOCH_ID)
        if account is not None:
            return account
        return await self._repository.create(
            user_id=user_id,
            epoch_id=GAME_EPOCH_ID,
            rule_version=RULES_VERSION,
            initial_cash_krw=INITIAL_CASH_KRW,
            game_day=game_day,
        )

    async def _guard_pending_limit(self, user_id: int) -> None:
        pending = await self._orders.list_pending(user_id, GAME_EPOCH_ID)
        if len(pending) >= MAX_PENDING_LIMIT_ORDERS:
            raise InvalidOrder(
                f"대기 주문은 동시에 {MAX_PENDING_LIMIT_ORDERS}개까지만 걸 수 있습니다"
            )

    @staticmethod
    def _guard_book_capacity(params, tick: int, spot_krw: int, side: str, quantity: int, extra) -> None:
        candles = price_engine.daily_candles(params, tick, 1, extra)
        volume = candles[-1].simulated_volume if candles else 1
        book = orderbook.build(params, spot_krw, tick, volume, price_engine.tick_size(spot_krw))
        if orderbook.fill(book, side, quantity, spot_krw).exhausted:
            raise InvalidOrder(
                "호가 잔량을 넘는 수량은 지정가로 예약할 수 없습니다(부분체결 없음)"
            )

    @staticmethod
    def _to_view(order: LimitOrderRecord, **overrides) -> LimitOrderView:
        params = find_symbol(order.symbol)
        fields = dict(
            id=order.id,
            kind=order.kind,
            symbol=order.symbol,
            name=params.name if params else order.symbol,
            side=order.side,
            position_id=order.position_id,
            trigger=order.trigger,
            limit_price_krw=order.limit_price_krw,
            quantity=order.quantity,
            leverage=order.leverage,
            placed_tick=order.placed_tick,
            expires_tick=order.expires_tick,
            status=order.status,
            filled_tick=order.filled_tick,
            filled_price_krw=order.filled_price_krw,
            reserved_cash_krw=order.reserved_cash_krw,
        )
        fields.update(overrides)
        return LimitOrderView(**fields)
