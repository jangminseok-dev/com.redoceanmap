from __future__ import annotations

from game.app.dtos.account_dto import Account
from game.app.dtos.wallet_dto import ClosedNotice, PositionView, WalletQuery, WalletView
from game.app.ports.input.wallet_use_case import WalletUseCase
from game.app.ports.output.game_account_repository import GameAccountRepository
from game.app.ports.output.game_clock_port import GameClockPort
from game.domain.clock.game_epoch import (
    GAME_EPOCH_ID,
    RULES_VERSION,
    SEASON_TICKS,
    TICKS_PER_GAME_DAY,
    describe,
)
from game.domain.market import futures_contract, price_engine
from game.domain.market.symbol_params import find as find_symbol
from game.domain.trading.liquidation import CloseHit, resolve_close
from game.domain.trading.trading_rules import (
    INITIAL_CASH_KRW,
    RESERVED_CASH_KRW,
    Side,
    close_result,
    investable_cash,
    liquidation_price,
)


class WalletInteractor(WalletUseCase):
    """지갑 대장 — 현금과 미청산 포지션을 현재 시세로 평가한다.

    평가액은 **지금 청산하면 돌아올 금액**이다(수수료·숏 보유비용 반영). 단순 시가평가보다
    보수적이지만, 유저가 실제로 손에 쥘 금액과 화면 숫자가 어긋나지 않는다.
    """

    def __init__(self, repository: GameAccountRepository, clock: GameClockPort) -> None:
        self._repository = repository
        self._clock = clock

    async def get_wallet(self, query: WalletQuery) -> WalletView:
        moment = describe(self._clock.now_tick())
        price_tick = min(moment.tick, SEASON_TICKS)

        account = await self._repository.load(query.user_id, GAME_EPOCH_ID)
        if account is None:
            account = await self._repository.create(
                user_id=query.user_id,
                epoch_id=GAME_EPOCH_ID,
                rule_version=RULES_VERSION,
                initial_cash_krw=INITIAL_CASH_KRW,
                game_day=moment.game_day,
            )

        # 조회가 곧 마감 시점이다 — 미접속 중 청산됐어야 할 포지션을 여기서 확정한다.
        # 확정이 있었으면 지갑·포지션이 바뀌므로 다시 읽는다.
        if await self._settle_due_positions(account, price_tick):
            account = await self._repository.load(query.user_id, GAME_EPOCH_ID) or account

        positions = tuple(self._evaluate(account, price_tick))
        position_value = sum(p.market_value_krw for p in positions)
        total = account.cash_krw + position_value
        notices = await self._recent_notices(query.user_id)

        return WalletView(
            cash_krw=account.cash_krw,
            investable_krw=investable_cash(account.cash_krw),
            reserved_krw=RESERVED_CASH_KRW,
            position_value_krw=position_value,
            total_asset_krw=total,
            initial_cash_krw=INITIAL_CASH_KRW,
            total_return_pct=round((total - INITIAL_CASH_KRW) / INITIAL_CASH_KRW * 100, 2),
            epoch_id=account.epoch_id,
            rule_version=account.rule_version,
            tick=moment.tick,
            game_day=moment.game_day,
            game_quarter=moment.game_quarter,
            season_over=moment.season_over,
            positions=positions,
            recently_closed=notices,
        )

    async def _recent_notices(self, user_id: int) -> tuple[ClosedNotice, ...]:
        """표시용 종목명을 채운다 — 리포지토리는 도메인 파라미터를 모른다."""
        rows = await self._repository.list_recently_closed(user_id, GAME_EPOCH_ID)
        out = []
        for row in rows:
            params = find_symbol(row.symbol)
            out.append(
                ClosedNotice(
                    id=row.id,
                    symbol=row.symbol,
                    name=params.name if params else row.symbol,
                    side=row.side,
                    quantity=row.quantity,
                    leverage=row.leverage,
                    closed_game_day=row.closed_game_day,
                    exit_price_krw=row.exit_price_krw,
                    realized_pnl_krw=row.realized_pnl_krw,
                    reason=row.reason,
                )
            )
        return tuple(out)

    async def _settle_due_positions(self, account: Account, price_tick: int) -> bool:
        """강제청산·만료를 확정한다. 하나라도 마감했으면 True.

        **멱등해야 한다.** 지갑은 30초마다 폴링되므로 같은 포지션을 두 번 마감하면 원장이
        어긋난다. 리포지토리가 `closed_tick IS NULL` + `FOR UPDATE`로 잠그므로 두 번째
        시도는 `LookupError`이고, 그건 "이미 처리됨"이라 삼킨다.
        """
        settled = False
        for position in account.open_positions:
            if position.leverage <= 1 or position.expires_tick is None:
                continue  # 1배는 마감 판정 대상이 아니다

            if position.instrument == "FUTURES":
                # 선물은 **틱 스캔을 하지 않는다.** 지수 평가가 종목의 13배라 같은 스캔이
                # 96ms가 되고, 만기 구간 변동(최대 7.99%)이 증거금 20%에 못 미쳐 중도
                # 청산 경로가 사실상 없다. 만기 도달만 본다.
                if price_tick < position.expires_tick:
                    continue
                hit = CloseHit(
                    tick=position.expires_tick,
                    price_krw=futures_contract.contract_value_krw(
                        futures_contract.settlement_price(position.expires_tick)
                    ),
                    reason="settled",
                )
            else:
                params = find_symbol(position.symbol)
                if params is None:
                    continue
                hit = resolve_close(
                    lambda tick: price_engine.price_at(params, tick),
                    side=Side(position.side),
                    entry_price_krw=position.entry_price_krw,
                    leverage=position.leverage,
                    entry_tick=position.entry_tick,
                    now_tick=price_tick,
                    expires_tick=position.expires_tick,
                )
            if hit is None:
                continue

            held_days = max(0.0, (hit.tick - position.entry_tick) / TICKS_PER_GAME_DAY)
            result = close_result(
                side=Side(position.side),
                entry_price_krw=position.entry_price_krw,
                exit_price_krw=hit.price_krw,
                quantity=position.quantity,
                holding_game_days=held_days,
                entry_fee_krw=position.entry_fee_krw,
                leverage=position.leverage,
                forced=hit.forced,
            )
            try:
                await self._repository.close_position(
                    user_id=account.user_id,
                    position_id=position.id,
                    closed_tick=hit.tick,
                    exit_price_krw=hit.price_krw,
                    exit_fee_krw=result.fee_krw,
                    carry_krw=result.carry_krw,
                    realized_pnl_krw=result.realized_pnl_krw,
                    proceeds_krw=result.proceeds_krw,
                    game_day=hit.tick // TICKS_PER_GAME_DAY,
                    close_reason=hit.reason,
                )
            except LookupError:
                continue  # 다른 요청이 먼저 마감했다 — 정상이다
            settled = True
        return settled

    def _evaluate(self, account: Account, price_tick: int):
        for position in account.open_positions:
            if position.instrument == "FUTURES":
                name, sector = "지수 선물", futures_contract.INDEX_CODE
                expiry = position.expires_tick or price_tick
                current = futures_contract.contract_value_krw(
                    futures_contract.futures_price(expiry, min(price_tick, expiry))
                )
            else:
                params = find_symbol(position.symbol)
                if params is None:
                    continue  # 시즌 교체로 종목이 사라진 경우 — 조용히 건너뛴다
                name, sector = params.name, params.sector
                current = price_engine.price_at(params, price_tick)
            held_days = max(0.0, (price_tick - position.entry_tick) / TICKS_PER_GAME_DAY)
            result = close_result(
                side=Side(position.side),
                entry_price_krw=position.entry_price_krw,
                exit_price_krw=current,
                quantity=position.quantity,
                holding_game_days=held_days,
                entry_fee_krw=position.entry_fee_krw,
                leverage=position.leverage,
            )
            notional = position.entry_price_krw * position.quantity
            margin = notional // position.leverage if position.leverage > 1 else notional
            invested = margin + position.entry_fee_krw
            yield PositionView(
                id=position.id,
                symbol=position.symbol,
                name=name,
                sector=sector,
                side=position.side,
                quantity=position.quantity,
                entry_tick=position.entry_tick,
                entry_price_krw=position.entry_price_krw,
                current_price_krw=current,
                market_value_krw=result.proceeds_krw,
                unrealized_pnl_krw=result.realized_pnl_krw,
                unrealized_pct=round(result.realized_pnl_krw / invested * 100, 2)
                if invested
                else 0.0,
                leverage=position.leverage,
                liquidation_price_krw=liquidation_price(
                    Side(position.side), position.entry_price_krw, position.leverage
                ),
                expires_tick=position.expires_tick,
            )
