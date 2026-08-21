from __future__ import annotations

from abc import ABC, abstractmethod

from stock.app.dtos.forecast_snapshot_dto import SnapshotScoreUpdate
from stock.domain.entities.forecast_snapshot import ForecastSnapshot


class ForecastSnapshotRepositoryPort(ABC):
    """예측 스냅샷 영속 아웃바운드 포트."""

    @abstractmethod
    async def save_many(self, snapshots: list[ForecastSnapshot]) -> int:
        """저장하고 신규 건수를 반환한다. (ticker, horizon_days, as_of) 중복은 무시."""
        ...

    @abstractmethod
    async def find_pending(self) -> list[ForecastSnapshot]:
        """미채점(evaluated_at IS NULL) 스냅샷 전부 — 채점 배치 입력."""
        ...

    @abstractmethod
    async def apply_scores(self, updates: list[SnapshotScoreUpdate]) -> int:
        """채점 결과를 반영하고 반영 건수를 반환한다."""
        ...

    # 아래 셋은 `signal_config`로 판정 조합을 좁힌다 — 조합이 다른 판정을 한 분모에 섞으면
    # 적중률·신호별 일치율이 서로 다른 규칙의 성적을 합친 숫자가 된다(2026-07-30 조합 교체).
    # None이면 전 조합(이력 전체 조회용).

    @abstractmethod
    async def find_scored(
        self, horizon: int | None, limit: int, signal_config: str | None = None
    ) -> list[ForecastSnapshot]:
        """채점 완료분(evaluated_at 내림차순) — 요약 집계 재료."""
        ...

    @abstractmethod
    async def find_recent(
        self, horizon: int | None, limit: int, signal_config: str | None = None
    ) -> list[ForecastSnapshot]:
        """최근 스냅샷(as_of 내림차순) — 어드민 목록."""
        ...

    @abstractmethod
    async def find_scored_all(self, horizon: int) -> list[ForecastSnapshot]:
        """채점 완료 전량(전 조합·limit 없음) — 재적합 표본.

        조합을 좁히지 않는 이유: 재적합은 저장된 판정이 아니라 동결 원신호(config 무관)로
        재채점하므로, NULL 조합(2026-07-30 이전) 표본을 빼면 표본 절반을 유실한다.
        """
        ...

    @abstractmethod
    async def counts(
        self, horizon: int | None, signal_config: str | None = None
    ) -> tuple[int, int]:
        """(전체, 채점 완료) 건수."""
        ...
