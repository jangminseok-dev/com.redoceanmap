from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class NewsEventStudyReportOrm(Base):
    """뉴스 이벤트 사후 수익률 연구 리포트 — 실행당 1행(집계 payload 문서).

    쓰기는 `scripts/study_news_events.py`(오프라인 배치), 조회는 어드민(최신 1건).
    `area_score_backtest_reports`와 같은 형태다 — 코퍼스 전역 집계라 요청마다 계산할
    것이 아니고, 결과는 "이 라벨러가 쓸모 있는가"에 대한 연구 결과이지 투자 정보가 아니다.

    payload 스키마의 단일 정의처는 `stock/domain/services/event_study.py`.
    """

    __tablename__ = "news_event_study_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    params: Mapped[dict] = mapped_column(JSONB)
    payload: Mapped[dict] = mapped_column(JSONB)
