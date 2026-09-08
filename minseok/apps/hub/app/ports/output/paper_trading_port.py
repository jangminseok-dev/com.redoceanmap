from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from hub.app.dtos.paper_trading_dto import PaperStepOutcome


class PaperTradingPort(ABC):
    """허브가 stock에 위임하는 모의투자 배치 추상 — cron의 일일 step·리플레이 창구."""

    @abstractmethod
    async def step(self, as_of: datetime, replay: bool) -> PaperStepOutcome:
        """as_of 기준으로 체결·평가·채점·판단을 한 바퀴 돌린다. 재실행 멱등."""
        ...
