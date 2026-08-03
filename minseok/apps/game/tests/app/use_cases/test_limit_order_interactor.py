"""지정가 주문 유스케이스 — 스텁 포트로 검증(mock 프레임워크 미사용).

가격은 실제 결정론 엔진을 그대로 쓴다. 대신 **닿을 수 없는 지정가**(1원)와
**언제나 닿는 지정가**(10억)로 체결 여부를 확정적으로 만든다 — 시세를 흉내 내지 않는다.
"""

import pytest

from game.app.dtos.account_dto import Account, OpenPosition
from game.app.dtos.limit_order_dto import (
    OrderActionCommand,
    OrderListQuery,
    PlaceEntryOrderCommand,
    PlaceExitOrderCommand,
)
from game.app.exceptions import InvalidOrder
from game.app.ports.output.game_limit_order_repository import LimitOrderRecord
from game.app.use_cases.limit_order_interactor import LimitOrderInteractor
from game.domain.clock.game_epoch import GAME_EPOCH_ID
from game.domain.market import price_engine
from game.domain.market.symbol_params import SYMBOLS

_SYMBOL = SYMBOLS[0].symbol
# 주문을 건 틱과 조회 틱이 같으면 스캔 구간이 비어 체결이 일어나지 않는다 — 실제로도
# "예약한 순간 체결"은 지정가가 아니라 시장가다. 그래서 두 시각을 벌려 둔다.
_PLACED_TICK = 30
_NOW_TICK = 40

# 스캔 구간의 최고가보다 위에 걸면 le는 반드시 체결된다(가격이 결정론이라 확정값이다).
_PEAK = max(
    price_engine.price_at(SYMBOLS[0], tick, None, ()) for tick in range(_PLACED_TICK + 1, _NOW_TICK + 1)
)
_FILLS_BUY = _PEAK * 2  # le(매수 예약)가 반드시 닿는 지정가
_NEVER = 1  # 어떤 틱에도 가격이 이 위다 → le는 절대 체결되지 않는다
_ALWAYS_UP = 1  # ge(익절 등)는 1원 이상이면 언제나 닿는다


class _StubClock:
    def __init__(self, tick: int = 30) -> None:
        self.tick = tick

    def now_tick(self) -> int:
        return self.tick


class _StubOrders:
    def __init__(self, records=()) -> None:
        self.records = list(records)
        self.filled: list[tuple[int, int, int]] = []
        self.closed: list[tuple[int, str]] = []
        self.cancelled_positions: list[tuple[int, int | None]] = []
        self.extended: list[tuple[int, int]] = []
        self._next_id = 100

    async def place(self, **kw) -> LimitOrderRecord:
        record = LimitOrderRecord(
            id=self._next_id,
            user_id=kw["user_id"],
            kind=kw["kind"],
            symbol=kw["symbol"],
            side=kw["side"],
            position_id=kw.get("position_id"),
            trigger=kw["trigger"],
            limit_price_krw=kw["limit_price_krw"],
            quantity=kw["quantity"],
            leverage=kw.get("leverage", 1),
            placed_tick=kw["placed_tick"],
            expires_tick=kw["expires_tick"],
            status="pending",
            filled_tick=None,
            filled_price_krw=None,
            reserved_cash_krw=kw.get("reserved_cash_krw", 0),
        )
        self._next_id += 1
        self.records.append(record)
        return record

    async def list_pending(self, user_id, epoch_id):
        return tuple(r for r in self.records if r.status == "pending")

    async def list_recent(self, user_id, epoch_id, limit=20):
        return tuple(r for r in self.records if r.status != "pending")

    async def find(self, user_id, order_id):
        return next((r for r in self.records if r.id == order_id), None)

    async def mark_filled(self, order_id, filled_tick, filled_price_krw):
        self.filled.append((order_id, filled_tick, filled_price_krw))
        self._set_status(order_id, "filled")

    async def mark_closed(self, order_id, status):
        self.closed.append((order_id, status))
        self._set_status(order_id, status)

    async def cancel_for_position(self, position_id, except_order_id=None):
        self.cancelled_positions.append((position_id, except_order_id))
        return 0

    async def extend(self, order_id, expires_tick):
        self.extended.append((order_id, expires_tick))

    def _set_status(self, order_id: int, status: str) -> None:
        self.records = [
            LimitOrderRecord(**{**r.__dict__, "status": status}) if r.id == order_id else r
            for r in self.records
        ]


class _StubAccounts:
    def __init__(self, cash_krw=10_000_000, positions=()) -> None:
        self.account = Account(
            user_id=7,
            cash_krw=cash_krw,
            epoch_id=GAME_EPOCH_ID,
            rule_version="v2",
            open_positions=tuple(positions),
        )
        self.cash_moves: list[tuple[int, str]] = []
        self.opened: list[dict] = []
        self.closed: list[dict] = []

    async def load(self, user_id, epoch_id):
        return self.account

    async def create(self, **kw):
        return self.account

    async def adjust_cash(self, user_id, epoch_id, amount_krw, game_day, source, **kw):
        self.cash_moves.append((amount_krw, source))
        return self.account.cash_krw + amount_krw

    async def open_position(self, **kw):
        self.opened.append(kw)
        return OpenPosition(
            id=1,
            symbol=kw["symbol"],
            side=kw["side"],
            quantity=kw["quantity"],
            entry_tick=kw["entry_tick"],
            entry_price_krw=kw["entry_price_krw"],
            entry_fee_krw=kw["entry_fee_krw"],
        )

    async def close_position(self, **kw):
        self.closed.append(kw)
        return None


def _position(**overrides) -> OpenPosition:
    base = dict(
        id=5,
        symbol=_SYMBOL,
        side="LONG",
        quantity=1,
        entry_tick=0,
        entry_price_krw=10_000,
        entry_fee_krw=20,
    )
    base.update(overrides)
    return OpenPosition(**base)


def _build(orders=None, accounts=None, tick=_PLACED_TICK):
    orders = orders or _StubOrders()
    accounts = accounts or _StubAccounts()
    return (
        LimitOrderInteractor(orders=orders, repository=accounts, clock=_StubClock(tick)),
        orders,
        accounts,
    )


async def test_진입_예약은_현금을_묶는다():
    interactor, orders, accounts = _build()

    receipt = await interactor.place_entry(
        PlaceEntryOrderCommand(user_id=7, symbol=_SYMBOL, side="LONG", quantity=1,
                               limit_price_krw=_NEVER)
    )

    assert receipt.orders[0].status == "pending"
    amount, source = accounts.cash_moves[0]
    assert amount < 0 and source == "limit_reserve"


async def test_조회가_체결_시점이다():
    """닿는 지정가를 걸어두면 다음 조회에서 포지션이 생긴다(cron 없음)."""
    interactor, orders, accounts = _build()
    await interactor.place_entry(
        PlaceEntryOrderCommand(user_id=7, symbol=_SYMBOL, side="LONG", quantity=1,
                               limit_price_krw=_FILLS_BUY)
    )
    interactor._clock.tick = _NOW_TICK  # 시간이 흘러야 판정할 구간이 생긴다

    result = await interactor.list_orders(OrderListQuery(user_id=7))

    assert result.settled_count == 1
    assert accounts.opened and accounts.opened[0]["entry_price_krw"] == _FILLS_BUY
    assert orders.filled and not result.pending
    # 묶은 돈을 풀고 실제 비용으로 다시 뺀다 — 원장에 두 줄이 남는다
    assert [s for _, s in accounts.cash_moves] == ["limit_reserve", "limit_release"]


async def test_체결되지_않으면_대기로_남는다():
    interactor, orders, accounts = _build()
    await interactor.place_entry(
        PlaceEntryOrderCommand(user_id=7, symbol=_SYMBOL, side="LONG", quantity=1,
                               limit_price_krw=_NEVER)
    )
    interactor._clock.tick = _NOW_TICK

    result = await interactor.list_orders(OrderListQuery(user_id=7))

    assert result.settled_count == 0 and len(result.pending) == 1
    assert not accounts.opened


async def test_취소는_묶인_돈을_돌려준다():
    interactor, orders, accounts = _build()
    receipt = await interactor.place_entry(
        PlaceEntryOrderCommand(user_id=7, symbol=_SYMBOL, side="LONG", quantity=1,
                               limit_price_krw=_NEVER)
    )

    await interactor.cancel(OrderActionCommand(user_id=7, order_id=receipt.orders[0].id))

    assert orders.closed[-1][1] == "cancelled"
    assert accounts.cash_moves[-1][1] == "limit_release"
    assert accounts.cash_moves[-1][0] > 0


async def test_만료된_주문은_돈을_돌려주고_닫는다():
    interactor, orders, accounts = _build()
    await interactor.place_entry(
        PlaceEntryOrderCommand(user_id=7, symbol=_SYMBOL, side="LONG", quantity=1,
                               limit_price_krw=_NEVER)
    )
    interactor._clock.tick = _PLACED_TICK + 181  # 만료 이후로 시계를 민다

    await interactor.list_orders(OrderListQuery(user_id=7))

    assert orders.closed[-1][1] == "expired"
    assert accounts.cash_moves[-1] == (accounts.cash_moves[0][0] * -1, "limit_release")


async def test_청산_예약_체결은_포지션을_닫고_나머지_예약을_취소한다():
    accounts = _StubAccounts(positions=[_position()])
    interactor, orders, _ = _build(accounts=accounts)
    # 익절(ge 1원)은 반드시 닿고, 손절(le 1원)은 절대 닿지 않는다 → 한쪽만 체결된다
    await interactor.place_exit(
        PlaceExitOrderCommand(user_id=7, position_id=5, take_profit_krw=_ALWAYS_UP,
                              stop_loss_krw=_NEVER)
    )
    interactor._clock.tick = _NOW_TICK

    await interactor.list_orders(OrderListQuery(user_id=7))

    assert accounts.closed and accounts.closed[0]["close_reason"] == "limit"
    assert accounts.closed[0]["exit_price_krw"] == _ALWAYS_UP
    # OCO — 체결된 주문을 뺀 나머지를 취소한다
    assert orders.cancelled_positions[-1][0] == 5
    assert orders.cancelled_positions[-1][1] is not None


async def test_강제청산이_지정가보다_우선한다():
    """같은 구간에서 청산이 먼저(또는 같은 틱에) 걸리면 예약은 무효다."""
    # 진입가를 극단으로 높인 4배 포지션 — 첫 스캔 틱에서 청산선을 이미 밑돈다
    accounts = _StubAccounts(
        positions=[_position(entry_price_krw=_PEAK * 100, leverage=4, expires_tick=210)]
    )
    interactor, orders, _ = _build(accounts=accounts)
    await interactor.place_exit(
        PlaceExitOrderCommand(user_id=7, position_id=5, take_profit_krw=_ALWAYS_UP)
    )
    interactor._clock.tick = _NOW_TICK

    await interactor.list_orders(OrderListQuery(user_id=7))

    assert not accounts.closed  # 예약이 포지션을 닫지 않았다
    assert orders.closed[-1][1] == "cancelled"


async def test_대기_주문_수에는_상한이_있다():
    """판정 비용이 주문 수에 비례한다 — 상한이 곧 성능 계약이다."""
    interactor, orders, _ = _build()
    for _ in range(20):
        await interactor.place_entry(
            PlaceEntryOrderCommand(user_id=7, symbol=_SYMBOL, side="LONG", quantity=1,
                                   limit_price_krw=_NEVER)
        )

    with pytest.raises(InvalidOrder):
        await interactor.place_entry(
            PlaceEntryOrderCommand(user_id=7, symbol=_SYMBOL, side="LONG", quantity=1,
                                   limit_price_krw=_NEVER)
        )


async def test_익절_손절이_없으면_거부한다():
    interactor, _, _ = _build(accounts=_StubAccounts(positions=[_position()]))
    with pytest.raises(InvalidOrder):
        await interactor.place_exit(PlaceExitOrderCommand(user_id=7, position_id=5))
