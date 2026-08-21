from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class ForecastRefitReportOrm(Base):
    """가중치 재적합 리포트 — 실행당 1행(리더보드·승격 판정 payload 문서).

    쓰기는 재적합 유스케이스(주 1회 배치 경유), 조회는 어드민(최신 1건).
    `news_event_study_reports`와 같은 형태다 — 표본 전량 재채점이라 요청마다 계산할
    것이 아니고, 게이트 미달 리포트도 저장한다(표본 축적 경과를 관측하는 재료).

    payload 스키마의 단일 정의처는 `stock/domain/services/weight_refit.py`의
    `RefitReport.to_payload()`.
    """

    __tablename__ = "forecast_refit_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    params: Mapped[dict] = mapped_column(JSONB)
    payload: Mapped[dict] = mapped_column(JSONB)
