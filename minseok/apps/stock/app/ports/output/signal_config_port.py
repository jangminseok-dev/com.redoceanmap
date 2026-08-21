from __future__ import annotations

from abc import ABC, abstractmethod

from stock.app.dtos.signal_config_dto import ActiveSignalConfig, ConfigHistoryRow
from stock.domain.entities.analysis_config import AnalysisConfig


class SignalConfigPort(ABC):
    """활성 판정 조합 아웃바운드 포트 — forecast·스냅샷·재적합이 공유한다.

    소비자가 요청마다 `active()`를 부른다(1행 SELECT, 별도 캐시 없음) —
    재적합 승격이 다음 요청부터 즉시 반영되게 하기 위한 의도적 선택이다.
    """

    @abstractmethod
    async def active(self) -> ActiveSignalConfig:
        """현재 활성 조합. 행이 없으면 코드 상수 폴백(마이그레이션 전 하위 호환)."""
        ...

    @abstractmethod
    async def activate(self, key: str, config: AnalysisConfig) -> None:
        """기존 활성 해제 + 새 조합 INSERT·활성 전환을 한 트랜잭션으로 수행한다."""
        ...

    @abstractmethod
    async def history(self) -> list[ConfigHistoryRow]:
        """조합 이력 전체(최신순) — 어드민 승격 이력 화면용."""
        ...
