from __future__ import annotations

from game.app.dtos.account_dto import Account
from game.app.dtos.wallet_dto import PositionView, WalletQuery, WalletView
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
from game.domain.market import price_engine
from game.domain.market.symbol_params import find as find_symbol
from game.domain.trading.trading_rules import (
    INITIAL_CASH_KRW,
    RESERVED_CASH_KRW,
    Side,
    close_result,
    investable_cash,
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

        positions = tuple(self._evaluate(account, price_tick))
        position_value = sum(p.market_value_krw for p in positions)
        total = account.cash_krw + position_value

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
        )

    def _evaluate(self, account: Account, price_tick: int):
        for position in account.open_positions:
            params = find_symbol(position.symbol)
            if params is None:
                continue  # 시즌 교체로 종목이 사라진 경우 — 조용히 건너뛴다
            current = price_engine.price_at(params, price_tick)
            held_days = max(0.0, (price_tick - position.entry_tick) / TICKS_PER_GAME_DAY)
            result = close_result(
                side=Side(position.side),
                entry_price_krw=position.entry_price_krw,
                exit_price_krw=current,
                quantity=position.quantity,
                holding_game_days=held_days,
                entry_fee_krw=position.entry_fee_krw,
            )
            invested = position.entry_price_krw * position.quantity + position.entry_fee_krw
            yield PositionView(
                id=position.id,
                symbol=position.symbol,
                name=params.name,
                sector=params.sector,
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
            )
