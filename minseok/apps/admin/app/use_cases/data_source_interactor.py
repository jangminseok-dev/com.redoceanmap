from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from admin.app.dtos.data_source_dto import DataSourceCard, DataSourceListResponse
from admin.app.ports.input.data_source_use_case import DataSourceUseCase
from admin.domain.services.dataset_freshness import evaluate
from hub.app.dtos.dataset_stat_dto import DatasetStat
from hub.app.ports.output.commercial_data_port import CommercialDataPort
from hub.app.ports.output.recommendation_directory_port import RecommendationDirectoryPort
from hub.app.ports.output.stock_dataset_stats_port import StockDatasetStatsPort


class DataSourceInteractor(DataSourceUseCase):
    """어드민 데이터소스 대장 — 상권·주식 데이터셋 현황에 수집 신선도 판정을 붙인다."""

    def __init__(
        self,
        commercial: CommercialDataPort,
        recommendations: RecommendationDirectoryPort,
        stock_stats: StockDatasetStatsPort,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._commercial = commercial
        self._recommendations = recommendations
        self._stock_stats = stock_stats
        self._now = now

    async def list_datasets(self) -> DataSourceListResponse:
        stats = list(await self._commercial.get_dataset_stats())
        rec_stats = await self._recommendations.stats()
        stats.append(
            DatasetStat(
                key="recommendations",
                name="추천 기록",
                row_count=rec_stats.total,
                latest_label=None,
            )
        )
        stats.extend(await self._stock_stats.get_dataset_stats())

        now = self._now()
        return DataSourceListResponse(datasets=[self._to_card(s, now) for s in stats])

    def _to_card(self, stat: DatasetStat, now: datetime) -> DataSourceCard:
        verdict = evaluate(stat.key, stat.latest_at, now)
        return DataSourceCard(
            key=stat.key,
            name=stat.name,
            row_count=stat.row_count,
            latest_label=stat.latest_label,
            latest_at=stat.latest_at,
            freshness=verdict.state.value,
            expected=verdict.expected,
            age_seconds=verdict.age_seconds,
        )
