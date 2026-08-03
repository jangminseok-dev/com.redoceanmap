from __future__ import annotations

from game.app.dtos.futures_dto import (
    CloseFuturesCommand,
    FuturesPositionView,
    FuturesQuery,
    FuturesReceipt,
    FuturesView,
    IndexPoint,
    OpenFuturesCommand,
)
from game.app.exceptions import (
    InsufficientCash,
    InvalidOrder,
    PositionNotFound,
    SeasonClosed,
)
from game.app.ports.input.futures_use_case import FuturesUseCase
from game.app.ports.output.game_account_repository import GameAccountRepository
from game.app.ports.output.game_clock_port import GameClockPort
from game.domain.clock.game_epoch import (
    GAME_EPOCH_ID,
    RULES_VERSION,
    SEASON_TICKS,
    TICKS_PER_GAME_DAY,
    describe,
)
from game.domain.market import futures_contract as fut
from game.domain.market import price_engine
from game.domain.trading.trading_rules import (
    INITIAL_CASH_KRW,
    Side,
    close_result,
    entry_cost,
    investable_cash,
)

MIN_TICKS = 2
MAX_TICKS = 240
MAX_CONTRACTS_PER_ORDER = 1_000  # 정수 오버플로·오타 방어
INDEX_SERIES_STEP = 6  # 지수는 1회 0.58ms라 매 틱을 그리지 않는다(240틱 → 40점)


class FuturesInteractor(FuturesUseCase):
    """지수 선물 대장.

    **중도 강제청산이 없다.** 만기(180틱) 구간의 지수 변동은 실측 표준편차 1.64%·최대 7.99%로
    증거금 20%에 못 미쳐, 손실 상한 클램프만으로 지갑이 음수가 되지 않는다. 대신 틱 스캔을
    두지 않으므로 지수 평가 비용(0.58ms)이 응답을 무너뜨리지 않는다.

    만기 정산은 **조회 시점에 확정된다** — 지갑 조회의 지연 마감 루프와 같은 경로다.
    """

    def __init__(self, repository: GameAccountRepository, clock: GameClockPort) -> None:
        self._repository = repository
        self._clock = clock

    async def get_market(self, query: FuturesQuery) -> FuturesView:
        if not MIN_TICKS <= query.ticks <= MAX_TICKS:
            raise InvalidOrder(f"ticks는 {MIN_TICKS}~{MAX_TICKS} 범위여야 합니다")

        moment = describe(self._clock.now_tick())
        tick = min(moment.tick, SEASON_TICKS)
        contract = fut.front_contract(tick)
        account = await self._load_or_create(query.user_id, moment.game_day)

        spot = price_engine.index_at(tick)
        futures_point = fut.futures_price(contract.expiry_tick, tick)
        contract_value = fut.contract_value_krw(futures_point)
        margin = round(contract_value * contract.margin_ratio)
        investable = investable_cash(account.cash_krw)

        start = max(0, tick - query.ticks + 1)
        series = tuple(
            IndexPoint(tick=t, point=price_engine.index_at(t))
            for t in range(start, tick + 1, INDEX_SERIES_STEP)
        )
        return FuturesView(
            virtual=True,
            contract_code=contract.code,
            expiry_tick=contract.expiry_tick,
            ticks_to_expiry=max(0, contract.expiry_tick - tick),
            index_point=spot,
            futures_point=futures_point,
            basis_pct=round((futures_point - spot) / spot * 100, 2) if spot else 0.0,
            contract_value_krw=contract_value,
            margin_per_contract_krw=margin,
            multiplier_krw=contract.multiplier_krw,
            margin_ratio=contract.margin_ratio,
            max_contracts=investable // margin if margin else 0,
            series=series,
            positions=tuple(self._positions(account, tick)),
            investable_krw=investable,
            tick=moment.tick,
            game_day=moment.game_day,
            game_quarter=moment.game_quarter,
            season_over=moment.season_over,
        )

    async def open(self, command: OpenFuturesCommand) -> FuturesReceipt:
        moment = describe(self._clock.now_tick())
        if moment.season_over:
            raise SeasonClosed("시즌이 종료되어 새로 진입할 수 없습니다")
        if command.contracts <= 0 or command.contracts > MAX_CONTRACTS_PER_ORDER:
            raise InvalidOrder("계약 수는 1 이상이어야 합니다")
        try:
            side = Side(command.side)
        except ValueError as e:
            raise InvalidOrder("방향은 LONG 또는 SHORT여야 합니다") from e

        contract = fut.front_contract(moment.tick)
        remaining = contract.expiry_tick - moment.tick
        if remaining < fut.MIN_TICKS_TO_EXPIRY:
            raise InvalidOrder(
                f"만기까지 {fut.MIN_TICKS_TO_EXPIRY}틱 미만인 계약에는 진입할 수 없습니다"
            )

        account = await self._load_or_create(command.user_id, moment.game_day)
        futures_point = fut.futures_price(contract.expiry_tick, moment.tick)
        price = fut.contract_value_krw(futures_point)  # 1계약 명목
        cost = entry_cost(price, command.contracts, fut.FUTURES_LEVERAGE)
        budget = investable_cash(account.cash_krw)
        if cost.total_krw > budget:
            raise InsufficientCash(
                f"증거금이 부족합니다 (필요 {cost.total_krw:,}원 · 가능 {budget:,}원)"
            )

        position = await self._repository.open_position(
            user_id=command.user_id,
            epoch_id=GAME_EPOCH_ID,
            symbol=contract.code,
            side=side.value,
            quantity=command.contracts,
            entry_tick=moment.tick,
            entry_price_krw=price,
            entry_fee_krw=cost.fee_krw,
            cash_delta_krw=-cost.total_krw,
            game_day=moment.game_day,
            instrument="FUTURES",
            leverage=fut.FUTURES_LEVERAGE,
            expires_tick=contract.expiry_tick,
        )
        return FuturesReceipt(
            position_id=position.id,
            contract_code=contract.code,
            side=side.value,
            contracts=command.contracts,
            price_krw=price,
            futures_point=futures_point,
            fee_krw=cost.fee_krw,
            margin_krw=cost.principal_krw,
            cash_delta_krw=-cost.total_krw,
            realized_pnl_krw=None,
            cash_krw=account.cash_krw - cost.total_krw,
            expires_tick=contract.expiry_tick,
            tick=moment.tick,
        )

    async def close(self, command: CloseFuturesCommand) -> FuturesReceipt:
        moment = describe(self._clock.now_tick())
        account = await self._repository.load(command.user_id, GAME_EPOCH_ID)
        if account is None:
            raise PositionNotFound("보유한 선물 포지션이 없습니다")
        position = next(
            (
                p
                for p in account.open_positions
                if p.id == command.position_id and p.instrument == "FUTURES"
            ),
            None,
        )
        if position is None:
            raise PositionNotFound("선물 포지션을 찾을 수 없거나 이미 마감됐습니다")

        expiry = position.expires_tick or moment.tick
        # 만기가 지났으면 그 시점의 **현물 정산가**로 확정한다(중도 청산이 아니라 만기 정산).
        settled = moment.tick >= expiry
        closed_tick = expiry if settled else moment.tick
        point = (
            fut.settlement_price(expiry)
            if settled
            else fut.futures_price(expiry, moment.tick)
        )
        price = fut.contract_value_krw(point)
        held_days = max(0.0, (closed_tick - position.entry_tick) / TICKS_PER_GAME_DAY)
        result = close_result(
            side=Side(position.side),
            entry_price_krw=position.entry_price_krw,
            exit_price_krw=price,
            quantity=position.quantity,
            holding_game_days=held_days,
            entry_fee_krw=position.entry_fee_krw,
            leverage=position.leverage,
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
            close_reason="settled" if settled else "user",
        )
        return FuturesReceipt(
            position_id=position.id,
            contract_code=position.symbol,
            side=position.side,
            contracts=position.quantity,
            price_krw=price,
            futures_point=point,
            fee_krw=result.fee_krw,
            margin_krw=position.entry_price_krw
            * position.quantity
            // max(1, position.leverage),
            cash_delta_krw=result.proceeds_krw,
            realized_pnl_krw=result.realized_pnl_krw,
            cash_krw=account.cash_krw + result.proceeds_krw,
            expires_tick=expiry,
            tick=moment.tick,
        )

    async def _load_or_create(self, user_id: int, game_day: int):
        account = await self._repository.load(user_id, GAME_EPOCH_ID)
        if account is None:
            account = await self._repository.create(
                user_id=user_id,
                epoch_id=GAME_EPOCH_ID,
                rule_version=RULES_VERSION,
                initial_cash_krw=INITIAL_CASH_KRW,
                game_day=game_day,
            )
        return account

    def _positions(self, account, tick: int):
        for position in account.open_positions:
            if position.instrument != "FUTURES":
                continue
            expiry = position.expires_tick or tick
            point = fut.futures_price(expiry, min(tick, expiry))
            current = fut.contract_value_krw(point)
            held_days = max(0.0, (min(tick, expiry) - position.entry_tick) / TICKS_PER_GAME_DAY)
            result = close_result(
                side=Side(position.side),
                entry_price_krw=position.entry_price_krw,
                exit_price_krw=current,
                quantity=position.quantity,
                holding_game_days=held_days,
                entry_fee_krw=position.entry_fee_krw,
                leverage=position.leverage,
            )
            margin = (
                position.entry_price_krw * position.quantity // max(1, position.leverage)
            )
            invested = margin + position.entry_fee_krw
            yield FuturesPositionView(
                id=position.id,
                contract_code=position.symbol,
                side=position.side,
                contracts=position.quantity,
                entry_price_krw=position.entry_price_krw,
                current_price_krw=current,
                market_value_krw=result.proceeds_krw,
                unrealized_pnl_krw=result.realized_pnl_krw,
                unrealized_pct=round(result.realized_pnl_krw / invested * 100, 2)
                if invested
                else 0.0,
                expires_tick=expiry,
                ticks_to_expiry=max(0, expiry - tick),
            )
