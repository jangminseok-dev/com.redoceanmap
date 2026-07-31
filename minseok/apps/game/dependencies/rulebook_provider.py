from __future__ import annotations

from game.adapter.outbound.log_rulebook_record_adapter import LogRulebookRecordAdapter
from game.adapter.outbound.system_game_clock_adapter import SystemGameClockAdapter
from game.app.ports.input.rulebook_use_case import RulebookUseCase
from game.app.use_cases.rulebook_interactor import RulebookInteractor


def get_rulebook_use_case() -> RulebookUseCase:
    return RulebookInteractor(
        record=LogRulebookRecordAdapter(),
        clock=SystemGameClockAdapter(),
    )
