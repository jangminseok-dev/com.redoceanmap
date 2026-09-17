"""상권 그래프 계약 DTO — Neo4j 투영(Area·Region·Industry·Article·Topic)에서 읽은 관계 사실."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AreaGraphInfo:
    trdar_code: int
    region_path: tuple[str, ...]        # 동 → 구 → 시 (IN_REGION 계층을 따라간 이름)
    sibling_area_count: int             # 같은 행정동(직속 Region)에 이어진 다른 상권 수
    industry_count: int                 # HAS_INDUSTRY로 이어진 업종 수(최신 분기 점포가 있는 업종)
    has_service: bool                   # 물은 업종이 이 상권에 이어져 있는가
    same_service_sibling_count: int     # 같은 행정동에서 같은 업종을 가진 다른 상권 수(그래프상 경쟁 상권)
    article_count: int                  # 상권명 어간과 맞는 Topic(area:태그)에 이어진 기사 수
