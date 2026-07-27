from datetime import datetime

from pydantic import BaseModel


class DatasetStatSchema(BaseModel):
    key: str
    name: str
    row_count: int
    latest_label: str | None
    latest_at: datetime | None
    freshness: str  # fresh · late · stale · unknown · unscheduled
    expected: str | None
    age_seconds: int | None


class DataSourceListResponseSchema(BaseModel):
    datasets: list[DatasetStatSchema]
