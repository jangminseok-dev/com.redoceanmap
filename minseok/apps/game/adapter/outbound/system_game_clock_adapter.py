"""현재 시각 → 게임 틱.

**이 저장소에서 game 앱이 `datetime.now()`를 호출하는 유일한 파일이다**(game-harness §1-1 · §8).
회귀 검증: `grep -rln "datetime.now\\|utcnow" minseok/apps/game` 결과가 1줄이어야 한다.
"""
from __future__ import annotations

from datetime import datetime, timezone

from game.app.ports.output.game_clock_port import GameClockPort
from game.domain.clock.game_epoch import tick_at


class SystemGameClockAdapter(GameClockPort):

    def now_tick(self) -> int:
        return tick_at(datetime.now(timezone.utc))
