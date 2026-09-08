from datetime import datetime

from pydantic import BaseModel


class PaperStepRequest(BaseModel):
    as_of: datetime | None = None  # 생략 시 지금. 리플레이는 과거 시각을 순서대로 넣는다
    replay: bool = False


class PaperStepResponse(BaseModel):
    as_of: datetime
    skipped: str | None
    filled: int
    decisions: int
    scored: int
    equity_rows: int
