from __future__ import annotations

from dataclasses import dataclass

from market.domain.value_objects.area_score_vo import AreaScore
from market.domain.value_objects.insight_vo import Insight


@dataclass(frozen=True)
class AreaIndexRow:
    """공개 인덱스(sitemap) 1행 — 서울시가 공개한 차원 데이터뿐. 지표·좌표는 싣지 않는다."""

    trdar_code: int
    trdar_name: str
    district_name: str
    division_name: str


@dataclass(frozen=True)
class AreaPublicView:
    """비로그인 공개 상권 페이지(A-4) — **필드를 명시적으로 고른다.**

    2026-09-14 사용자 결정: 핵심 요약 + 해석 문장. 좌표·인허가 상호 목록·인구 피라미드·
    업종 랭킹 표·소비 카테고리·매출 요일/시간 분해는 넣지 않는다(1,650페이지 크롤링으로
    로그인 데이터셋이 복제되지 않게). 필드를 늘리는 것은 보안 결정 — tests/test_public_routes.py.
    """

    trdar_code: int
    trdar_name: str
    district_name: str
    division_name: str
    year_quarter: int | None            # 기준 분기 — 매출·통행 팩트가 전혀 없으면 None
    score: AreaScore | None             # 종합점수·등급·컴포넌트 — 산출 팩트 없으면 None
    service_code: str | None            # 기준 업종(최신 분기 매출 최대) — 매출 없으면 None
    service_name: str | None
    store_count: int | None
    sales_per_store: int | None         # 원/월
    sales_qoq: float | None             # %
    closure_rate: float | None          # %
    floating_pop: int | None            # 주중+주말 통행 인구
    insights: list[Insight]
