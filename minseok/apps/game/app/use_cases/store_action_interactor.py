from __future__ import annotations

from game.app.dtos.store_action_dto import (
    CloseStoreCommand,
    CloseStoreReceipt,
    StoreDecisionCommand,
    StoreDecisionReceipt,
)
from game.app.exceptions import InsufficientCash, InvalidOrder, SeasonClosed, StoreNotFound
from game.app.ports.input.store_action_use_case import StoreActionUseCase
from game.app.ports.output.game_account_repository import GameAccountRepository
from game.app.ports.output.game_clock_port import GameClockPort
from game.app.ports.output.game_store_repository import GameStoreRepository
from game.domain.clock.game_epoch import GAME_EPOCH_ID, describe
from game.domain.commerce import settlement as settlement_rules
from game.domain.commerce import store_simulation as sim
from game.domain.trading.trading_rules import investable_cash

MAX_STAFF = 20
MIN_PRICE_FACTOR = 0.6
MAX_PRICE_FACTOR = 1.3
MAX_FACILITY_SCORE = 2_000


class StoreActionInteractor(StoreActionUseCase):
    """운영 대장 — 창업 이후의 결정과 폐업.

    **결정은 내일부터 적용된다.** 오늘 이전을 바꾸면 이미 확정된 분기 결산과 재계산 결과가
    어긋난다(일별 매출은 저장하지 않고 결정 이력으로 매번 다시 계산하기 때문이다).

    결정을 덮어쓰지 않고 쌓는 것도 같은 이유다 — 과거는 그때의 결정으로 재현되어야 한다.
    """

    def __init__(
        self,
        stores: GameStoreRepository,
        accounts: GameAccountRepository,
        clock: GameClockPort,
    ) -> None:
        self._stores = stores
        self._accounts = accounts
        self._clock = clock

    async def decide(self, command: StoreDecisionCommand) -> StoreDecisionReceipt:
        moment = describe(self._clock.now_tick())
        if moment.season_over:
            raise SeasonClosed("시즌이 종료되어 더 이상 운영을 바꿀 수 없습니다")

        store = await self._stores.find_store(command.user_id, command.store_id, GAME_EPOCH_ID)
        if store is None:
            raise StoreNotFound("가게를 찾을 수 없습니다")
        if store.status != "open":
            raise InvalidOrder("이미 폐업한 가게입니다")

        current = _effective_decision(store, moment.game_day)
        effective_from = moment.game_day + 1
        if any(d.effective_from_day >= effective_from for d in store.decisions):
            raise InvalidOrder("오늘은 이미 운영을 바꿨습니다. 내일 다시 조정할 수 있습니다")

        price_factor = (
            current.price_factor if command.price_factor is None else command.price_factor
        )
        staff_count = current.staff_count if command.staff_count is None else command.staff_count
        facility_score = (
            current.facility_score if command.facility_score is None else command.facility_score
        )

        if not MIN_PRICE_FACTOR <= price_factor <= MAX_PRICE_FACTOR:
            raise InvalidOrder(
                f"가격 계수는 {MIN_PRICE_FACTOR}~{MAX_PRICE_FACTOR} 범위여야 합니다"
            )
        if not 0 <= staff_count <= MAX_STAFF:
            raise InvalidOrder(f"직원 수는 0~{MAX_STAFF}명이어야 합니다")
        if facility_score < current.facility_score:
            # 되팔 수 없는 지출이라 줄이는 것을 허용하면 인테리어비를 환급해야 한다
            raise InvalidOrder("시설은 줄일 수 없습니다 — 이미 들어간 인테리어비는 회수되지 않습니다")
        if facility_score > MAX_FACILITY_SCORE:
            raise InvalidOrder(f"시설 점수는 최대 {MAX_FACILITY_SCORE}점입니다")

        added = facility_score - current.facility_score
        cost = sim.interior_cost(added, store.store_scale) if added else 0

        account = await self._accounts.load(command.user_id, GAME_EPOCH_ID)
        if account is None:
            raise StoreNotFound("지갑을 찾을 수 없습니다")
        if cost > investable_cash(account.cash_krw):
            raise InsufficientCash(
                f"시설 {added}점을 올리려면 {cost:,}원이 필요합니다 "
                f"(투자 가능 {investable_cash(account.cash_krw):,}원)"
            )

        await self._stores.add_decision(
            user_id=command.user_id,
            store_id=store.id,
            epoch_id=GAME_EPOCH_ID,
            effective_from_day=effective_from,
            price_factor=price_factor,
            staff_count=staff_count,
            facility_score=facility_score,
            interior_cost_krw=cost,
        )
        return StoreDecisionReceipt(
            store_id=store.id,
            effective_from_day=effective_from,
            price_factor=price_factor,
            staff_count=staff_count,
            facility_score=facility_score,
            facility_added=added,
            interior_cost_krw=cost,
            cash_delta_krw=-cost,
            cash_krw=account.cash_krw - cost,
        )

    async def close(self, command: CloseStoreCommand) -> CloseStoreReceipt:
        moment = describe(self._clock.now_tick())
        store = await self._stores.find_store(command.user_id, command.store_id, GAME_EPOCH_ID)
        if store is None:
            raise StoreNotFound("가게를 찾을 수 없습니다")
        if store.status != "open":
            raise InvalidOrder("이미 폐업한 가게입니다")

        account = await self._accounts.load(command.user_id, GAME_EPOCH_ID)
        if account is None:
            raise StoreNotFound("지갑을 찾을 수 없습니다")

        # 시즌이 끝나도 폐업은 막지 않는다 — 막으면 보증금이 영원히 잠긴다(청산과 같은 이유).
        # `describe()`가 이미 마지막 게임일로 클램프한다.
        closed_day = moment.game_day
        refund = store.deposit_krw
        await self._stores.close_store(
            user_id=command.user_id,
            store_id=store.id,
            epoch_id=GAME_EPOCH_ID,
            closed_game_day=closed_day,
            deposit_refund_krw=refund,
        )
        pending = settlement_rules.pending_quarters(
            opened_game_day=store.opened_game_day,
            settled_through_day=store.settled_through_day,
            today=moment.game_day,
            closed_game_day=closed_day,
        )
        return CloseStoreReceipt(
            store_id=store.id,
            closed_game_day=closed_day,
            deposit_refund_krw=refund,
            interior_lost_krw=store.interior_krw,
            cash_delta_krw=refund,
            cash_krw=account.cash_krw + refund,
            pending_settlement=bool(pending),
        )


def _effective_decision(store, game_day: int):
    """`game_day` 시점에 유효한 결정 — 재계산 쪽(store_daily·settlement)과 같은 규칙."""
    applicable = [d for d in store.decisions if d.effective_from_day <= game_day]
    if not applicable:
        return store.decisions[0]
    return max(applicable, key=lambda d: d.effective_from_day)
