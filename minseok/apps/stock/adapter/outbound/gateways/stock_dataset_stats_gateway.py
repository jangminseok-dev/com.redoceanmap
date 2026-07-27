from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from hub.app.dtos.dataset_stat_dto import DatasetStat
from hub.app.ports.output.stock_dataset_stats_port import StockDatasetStatsPort
from stock.adapter.outbound.orm.forecast_snapshot_orm import ForecastSnapshotOrm
from stock.adapter.outbound.orm.fundamental_snapshot_orm import FundamentalSnapshotOrm
from stock.adapter.outbound.orm.news_article_orm import NewsArticleOrm
from stock.adapter.outbound.orm.news_label_orm import NewsLabelOrm
from stock.adapter.outbound.orm.price_bar_orm import PriceBarOrm

# 표시명은 데이터를 소유한 스포크가 준다(market 게이트웨이 선례).
_DATASETS = (
    ("news_articles", "종목 뉴스", NewsArticleOrm),
    ("news_labels", "뉴스 라벨", NewsLabelOrm),
    ("fundamental_snapshots", "펀더멘털 스냅샷", FundamentalSnapshotOrm),
    ("forecast_snapshots", "예측 스냅샷", ForecastSnapshotOrm),
    ("price_bars", "주가 봉(OHLCV)", PriceBarOrm),
)


class StockDatasetStatsGateway(StockDatasetStatsPort):
    """허브 StockDatasetStatsPort 구현 — stock 소유 5개 테이블의 적재 현황을 집계한다.

    신선도 기준은 `created_at`(적재 시각)이다. 봉 시각(`price_bars.ts`)이나
    예측 기준일(`forecast_snapshots.as_of`)은 도메인 시각이라 수집이 멈춰도 정상으로 보인다.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_dataset_stats(self) -> list[DatasetStat]:
        stats: list[DatasetStat] = []
        for key, name, orm in _DATASETS:
            row = (await self._session.execute(
                select(func.count(orm.id), func.max(orm.created_at))
            )).one()
            stats.append(DatasetStat(
                key=key, name=name, row_count=row[0], latest_label=None, latest_at=row[1]
            ))
        return stats
