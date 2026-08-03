"""현재 틱에 걸려 있는 관리자 개입을 시장 이벤트로 읽어 온다.

시세를 만지는 유스케이스가 넷(시세·지갑·매매·선물)인데 넷 다 같은 것을 같은 방식으로
읽어야 한다 — **한 곳이라도 빠지면 화면 가격과 체결가가 갈라진다.** 그 한 줄을 여기 모은다.

리포지토리를 옵셔널로 두는 이유: 개입은 게임의 예외적 부가 기능이고, 순수 결정론만으로
돌아가는 경로(도메인 테스트·스텁)가 그대로 유지되어야 한다. `None`이면 빈 튜플이라
가격 계산이 개입 도입 전과 완전히 같아진다.
"""
from __future__ import annotations

from game.app.ports.output.game_intervention_repository import GameInterventionRepository
from game.domain.clock.game_epoch import GAME_EPOCH_ID
from game.domain.market import market_events
from game.domain.market import price_intervention as intervention_rules


async def load_active(
    repository: GameInterventionRepository | None, tick: int
) -> tuple[market_events.MarketEvent, ...]:
    """`tick` 시점 가격에 기여하는 개입들. 없거나 저장소가 없으면 빈 튜플."""
    if repository is None:
        return ()
    rows = await repository.list_in_window(
        GAME_EPOCH_ID, tick, market_events.EVENT_WINDOW_TICKS
    )
    return intervention_rules.to_events(rows)
