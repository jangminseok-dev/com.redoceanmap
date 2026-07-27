from datetime import datetime, timedelta, timezone

from admin.app.use_cases.data_source_interactor import DataSourceInteractor
from hub.app.dtos.dataset_stat_dto import DatasetStat
from hub.app.dtos.recommendation_directory_dto import RecommendationStats

NOW = datetime(2026, 7, 27, 12, tzinfo=timezone.utc)


class _StubCommercial:
    async def get_dataset_stats(self):
        return [
            DatasetStat(key="store", name="점포 현황", row_count=500, latest_label="20251"),
            DatasetStat(
                key="market_news",
                name="상권 뉴스",
                row_count=1267,
                latest_label=None,
                latest_at=NOW - timedelta(hours=2),
            ),
        ]


class _StubRecommendations:
    async def stats(self):
        return RecommendationStats(total=77, today=1, monthly=[], top_categories=[])


class _StubStockStats:
    def __init__(self, news_latest_at):
        self._news_latest_at = news_latest_at

    async def get_dataset_stats(self):
        return [
            DatasetStat(
                key="news_articles",
                name="종목 뉴스",
                row_count=22026,
                latest_label=None,
                latest_at=self._news_latest_at,
            ),
            DatasetStat(
                key="price_bars",
                name="주가 봉(OHLCV)",
                row_count=951762,
                latest_label=None,
                latest_at=NOW - timedelta(hours=1),
            ),
        ]


def _interactor(news_latest_at):
    return DataSourceInteractor(
        commercial=_StubCommercial(),
        recommendations=_StubRecommendations(),
        stock_stats=_StubStockStats(news_latest_at),
        now=lambda: NOW,
    )


async def test_상권_추천_주식_현황을_순서대로_이어붙인다():
    result = await _interactor(NOW - timedelta(minutes=10)).list_datasets()
    keys = [d.key for d in result.datasets]
    assert keys == ["store", "market_news", "recommendations", "news_articles", "price_bars"]
    assert result.datasets[2].row_count == 77
    assert result.datasets[3].row_count == 22026


async def test_주기_있는_데이터셋에_신선도가_붙는다():
    result = await _interactor(NOW - timedelta(minutes=10)).list_datasets()
    by_key = {d.key: d for d in result.datasets}
    assert by_key["news_articles"].freshness == "fresh"
    assert by_key["news_articles"].expected == "30분마다"
    assert by_key["news_articles"].age_seconds == 600
    assert by_key["market_news"].freshness == "fresh"
    assert by_key["price_bars"].freshness == "fresh"


async def test_정적_데이터셋은_판정하지_않는다():
    result = await _interactor(NOW).list_datasets()
    by_key = {d.key: d for d in result.datasets}
    for key in ("store", "recommendations"):
        assert by_key[key].freshness == "unscheduled"
        assert by_key[key].expected is None
        assert by_key[key].age_seconds is None
    assert by_key["store"].latest_label == "20251"  # 분기 라벨은 그대로 보존


async def test_수집이_멈추면_정지로_뜬다_2026_07_25_사고():
    result = await _interactor(NOW - timedelta(days=2, hours=6)).list_datasets()
    by_key = {d.key: d for d in result.datasets}
    assert by_key["news_articles"].freshness == "stale"


async def test_적재_이력이_없으면_불명():
    result = await _interactor(None).list_datasets()
    by_key = {d.key: d for d in result.datasets}
    assert by_key["news_articles"].freshness == "unknown"
    assert by_key["news_articles"].age_seconds is None
