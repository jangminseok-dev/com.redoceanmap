from __future__ import annotations

from fastapi import Depends

from admin.app.ports.input.data_source_use_case import DataSourceUseCase
from admin.app.use_cases.data_source_interactor import DataSourceInteractor
from hub.app.ports.output.commercial_data_port import CommercialDataPort
from hub.app.ports.output.recommendation_directory_port import RecommendationDirectoryPort
from hub.app.ports.output.stock_dataset_stats_port import StockDatasetStatsPort
from hub.dependencies.commercial_data_provider import get_commercial_data_port
from hub.dependencies.recommendation_directory_provider import get_recommendation_directory_port
from hub.dependencies.stock_dataset_stats_provider import get_stock_dataset_stats_port


def get_data_source_use_case(
    commercial: CommercialDataPort = Depends(get_commercial_data_port),
    recommendations: RecommendationDirectoryPort = Depends(get_recommendation_directory_port),
    stock_stats: StockDatasetStatsPort = Depends(get_stock_dataset_stats_port),
) -> DataSourceUseCase:
    return DataSourceInteractor(
        commercial=commercial, recommendations=recommendations, stock_stats=stock_stats
    )
