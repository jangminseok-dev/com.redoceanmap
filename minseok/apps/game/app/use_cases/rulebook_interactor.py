from __future__ import annotations

import logging

from game.app.dtos.rulebook_dto import RulebookQuery, RulebookResponse
from game.app.ports.input.rulebook_use_case import RulebookUseCase
from game.app.ports.output.game_clock_port import GameClockPort
from game.app.ports.output.rulebook_record_port import RulebookRecordPort
from game.domain.clock.game_epoch import (
    GAME_EPOCH_ID,
    RULES_VERSION,
    TICKS_PER_GAME_DAY,
    describe,
)
from game.domain.trading.trading_rules import (
    FEE_RATE,
    INITIAL_CASH_KRW,
    RESERVED_CASH_KRW,
    SHORT_CARRY_RATE_PER_GAME_DAY,
)

logger = logging.getLogger(__name__)

_INTRODUCTION = (
    "모의 투자와 상권 창업을 시뮬레이션합니다. "
    "GET /game/market/prices — 게임 종목의 가격 곡선을 냅니다. "
    "주가는 실제 시세가 아니라 서버가 생성한 가상값이며, 종목명도 가상 회사입니다"
    "(업종만 실제 시장에서 가져왔습니다). "
    "실제 매매를 실행하지 않고 증권사·계좌와 연동하지 않습니다. "
    "게임 시각은 실제 1시간이 게임 1일이며, 접속하지 않는 동안에도 흐릅니다. "
    "한 시즌은 게임 8분기(현실 약 30일)이고 종료 시 전원 초기 자본으로 재시작합니다. "
    "상권 매출은 서울시 상권분석서비스 실데이터를 근거로 계산하지만, "
    "임대료·인건비·원가는 공개 데이터가 없어 게임 규칙으로 산정한 가정치입니다."
)


class RulebookInteractor(RulebookUseCase):
    """게임 (game) 대장 — 규칙 안내와 현재 게임 시각을 함께 낸다."""

    def __init__(self, record: RulebookRecordPort, clock: GameClockPort) -> None:
        self._record = record
        self._clock = clock

    async def introduce_myself(self, query: RulebookQuery) -> RulebookResponse:
        await self._record.record(subject="introduce_myself", note=f"{query.name} 자기소개 관찰")
        now = describe(self._clock.now_tick())
        return RulebookResponse(
            id=query.id,
            name=query.name,
            introduction=_INTRODUCTION,
            epoch_id=GAME_EPOCH_ID,
            rule_version=RULES_VERSION,
            tick=now.tick,
            game_day=now.game_day,
            game_quarter=now.game_quarter,
            day_of_quarter=now.day_of_quarter,
            season_over=now.season_over,
            ticks_remaining=now.ticks_remaining,
            initial_cash_krw=INITIAL_CASH_KRW,
            reserved_cash_krw=RESERVED_CASH_KRW,
            fee_rate=FEE_RATE,
            short_carry_rate_per_game_day=SHORT_CARRY_RATE_PER_GAME_DAY,
            ticks_per_game_day=TICKS_PER_GAME_DAY,
        )
