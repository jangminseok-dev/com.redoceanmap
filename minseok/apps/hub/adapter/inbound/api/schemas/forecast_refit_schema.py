from __future__ import annotations

from pydantic import BaseModel


class RefitRunRequest(BaseModel):
    # False면 리더보드 계산·리포트 저장까지만(dry-run — 승격만 생략)
    promote: bool = True


class RefitRunResponse(BaseModel):
    promoted: bool
    activated_key: str | None
    reasons: list[str]
