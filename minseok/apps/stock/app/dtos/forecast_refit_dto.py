from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RefitRunResult:
    """재적합 실행 1회 결과 — 자동화 응답용 요약(상세는 리포트 payload)."""

    promoted: bool
    activated_key: str | None    # 승격 시 새 활성 조합 키(refit-YYYYMMDD)
    reasons: list[str]           # 승격/보류 사유


@dataclass(frozen=True)
class RefitReportView:
    """저장된 재적합 리포트 1건 — payload 키는 weight_refit.RefitReport.to_payload()가 정의."""

    ran_at: datetime
    params: dict
    payload: dict
