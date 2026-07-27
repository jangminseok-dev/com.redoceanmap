from fastapi import APIRouter, Depends

from admin.adapter.inbound.api.schemas.data_source_schema import (
    DataSourceListResponseSchema,
    DatasetStatSchema,
)
from admin.app.ports.input.data_source_use_case import DataSourceUseCase
from admin.dependencies.data_source_provider import get_data_source_use_case
from core.security import require_permission

data_source_router = APIRouter(prefix="/admin", tags=["admin"])


@data_source_router.get(
    "/data-sources",
    response_model=DataSourceListResponseSchema,
    dependencies=[Depends(require_permission("datasources:read"))],
)
async def list_data_sources(
    use_case: DataSourceUseCase = Depends(get_data_source_use_case),
) -> DataSourceListResponseSchema:
    result = await use_case.list_datasets()
    return DataSourceListResponseSchema(
        datasets=[
            DatasetStatSchema(
                key=d.key,
                name=d.name,
                row_count=d.row_count,
                latest_label=d.latest_label,
                latest_at=d.latest_at,
                freshness=d.freshness,
                expected=d.expected,
                age_seconds=d.age_seconds,
            )
            for d in result.datasets
        ]
    )
