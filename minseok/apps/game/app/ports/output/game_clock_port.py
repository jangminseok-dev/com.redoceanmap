"""현재 게임 틱 조회 포트.

도메인은 `tick: int`만 받는다 — 현재 시각을 읽는 것은 어댑터의 일이다(game-harness §1-1).
이 포트가 그 경계이며, 구현이 `datetime.now()`를 호출하는 유일한 자리다.
테스트는 고정 틱을 돌려주는 스텁으로 갈아끼운다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class GameClockPort(ABC):

    @abstractmethod
    def now_tick(self) -> int:
        """에포크 기준 현재 틱. CPU-bound라 동기 메서드다."""
        ...
