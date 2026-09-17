from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BoardStockStatus(BaseModel):
    """종목의 '지금' — 동결 스냅샷 기준. 매수 추천이 아니라 신호 관측이다."""

    ticker: str                  # 실제 저장 티커(표시·딥링크용)
    as_of: datetime              # 신호 기준일
    direction: str               # UP | DOWN | NEUTRAL
    price: float                 # 최신 수집 종가 — 준실시간 아님
    change_pct: float | None     # 전일 대비(0.02 = +2%)
    ready: bool                  # 검증 참고 신호(통계적 유의) 여부
    price_as_of: datetime | None


class BoardAreaStatus(BaseModel):
    """상권의 '지금' — 서울 중앙 상권 대비 종합점수 + 전분기 대비 매출 변화(점수 추이의 최신 QoQ)."""

    total: float                 # 종합점수(50점 = 서울 평균 수준)
    grade: str                   # 우수 / 양호 / 보통 / 주의 / 위험
    sales_qoq_pct: float | None  # 상권 매출 전분기 대비(%)
    seoul_qoq_pct: float | None  # 점수 v2 이후 항상 None(호환 유지 — 프론트가 null이면 숨긴다)


class BookmarkBoardItemResponse(BaseModel):
    id: int
    target_type: str
    target_key: str
    label: str
    created_at: datetime
    stock: BoardStockStatus | None = None
    area: BoardAreaStatus | None = None


class BookmarkBoardResponse(BaseModel):
    items: list[BookmarkBoardItemResponse]


class BookmarkBoardMyselfResponse(BaseModel):
    name: str
    description: str
    endpoints: list[str]
