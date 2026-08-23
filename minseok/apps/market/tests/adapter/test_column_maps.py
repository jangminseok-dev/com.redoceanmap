"""column_maps 검증(③-M5) — API 코드 맵과 CSV 한글 맵이 같은 ORM 컬럼 집합을 가리키는지.

자동 수집기(collect_seoul_quarter.py)는 API 맵으로 받고 CSV 맵의 역방향으로 파일을
재생성한다 — 두 맵이 어긋나면 컬럼이 **조용히 결측**된다. 오타·누락을 여기서 잡는다.
"""
from __future__ import annotations

import pytest

from market.adapter.outbound.csv.column_maps import (
    COMMERCIAL_CHANGE_API_COLUMN_MAP,
    COMMERCIAL_CHANGE_COLUMN_MAP,
    ESTIMATED_SALES_API_COLUMN_MAP,
    ESTIMATED_SALES_COLUMN_MAP,
    FLOATING_POPULATION_API_COLUMN_MAP,
    FLOATING_POPULATION_COLUMN_MAP,
    RESIDENT_POPULATION_API_COLUMN_MAP,
    RESIDENT_POPULATION_COLUMN_MAP,
    STORE_API_COLUMN_MAP,
    STORE_COLUMN_MAP,
    WORKING_POPULATION_API_COLUMN_MAP,
    WORKING_POPULATION_COLUMN_MAP,
)

_PAIRS = [
    ("estimated_sales", ESTIMATED_SALES_API_COLUMN_MAP, ESTIMATED_SALES_COLUMN_MAP),
    ("store", STORE_API_COLUMN_MAP, STORE_COLUMN_MAP),
    ("floating_population", FLOATING_POPULATION_API_COLUMN_MAP, FLOATING_POPULATION_COLUMN_MAP),
    ("resident_population", RESIDENT_POPULATION_API_COLUMN_MAP, RESIDENT_POPULATION_COLUMN_MAP),
    ("working_population", WORKING_POPULATION_API_COLUMN_MAP, WORKING_POPULATION_COLUMN_MAP),
    ("commercial_change", COMMERCIAL_CHANGE_API_COLUMN_MAP, COMMERCIAL_CHANGE_COLUMN_MAP),
]


@pytest.mark.parametrize("fact, api_map, csv_map", _PAIRS, ids=[p[0] for p in _PAIRS])
def test_API_맵과_CSV_맵은_같은_ORM_컬럼_집합이다(fact, api_map, csv_map):
    assert set(api_map.values()) == set(csv_map.values()), (
        f"{fact}: API 전용 {set(api_map.values()) - set(csv_map.values())}"
        f" · CSV 전용 {set(csv_map.values()) - set(api_map.values())}"
    )


@pytest.mark.parametrize("fact, api_map, csv_map", _PAIRS, ids=[p[0] for p in _PAIRS])
def test_맵_안에서_ORM_컬럼이_중복되지_않는다(fact, api_map, csv_map):
    # 값 중복 = 서로 다른 원본 컬럼이 같은 ORM 컬럼을 덮어씀(마지막 것만 남는 조용한 유실)
    for name, mapping in (("API", api_map), ("CSV", csv_map)):
        values = list(mapping.values())
        assert len(values) == len(set(values)), f"{fact} {name} 맵에 중복 ORM 컬럼"
