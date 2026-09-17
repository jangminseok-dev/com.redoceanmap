"""시도 벤치마크 캐시 — 상권마다 43.9만 행을 재집계하지 않는다.

벤치마크는 상권과 무관하게 같은 값인데 `/score` 요청마다 다시 계산됐다(실측 55,977 버퍼로
5행). 최신 분기를 버전 키로 삼아 분기 적재 때만 갱신되게 고정한다.
"""
import pytest

from market.adapter.outbound.pg import area_score_pg_repository as mod
from market.adapter.outbound.pg.area_score_pg_repository import AreaScorePgRepository


class _FakeOrm:
    """`_latest_quarter`가 `fact_orm.year_quarter`를 참조하므로 속성만 흉내낸다."""

    year_quarter = "year_quarter"


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _FakeSession:
    """`max(year_quarter)` 조회만 응답하는 세션 대역 — 버전 키 검증용."""

    def __init__(self, version):
        self.version = version
        self.version_calls = 0

    async def execute(self, stmt):
        self.version_calls += 1
        return _FakeResult(self.version)


@pytest.fixture(autouse=True)
def _clear_cache():
    mod._CITY_CACHE.clear()
    yield
    mod._CITY_CACHE.clear()


async def test_같은_분기면_재집계하지_않는다():
    session = _FakeSession(version=20254)
    repo = AreaScorePgRepository(session=session)
    calls = []

    async def compute():
        calls.append(1)
        return ["결과"]

    first = await repo._cached_city(("sales", "11", 5), _FakeOrm, compute)
    second = await repo._cached_city(("sales", "11", 5), _FakeOrm, compute)

    assert first == second == ["결과"]
    assert len(calls) == 1, "두 번째 호출은 캐시에서 와야 한다"


async def test_분기가_바뀌면_다시_집계한다():
    session = _FakeSession(version=20254)
    repo = AreaScorePgRepository(session=session)
    calls = []

    async def compute():
        calls.append(1)
        return [f"결과{len(calls)}"]

    await repo._cached_city(("sales", "11", 5), _FakeOrm, compute)
    session.version = 20261  # 새 분기 적재
    result = await repo._cached_city(("sales", "11", 5), _FakeOrm, compute)

    assert len(calls) == 2
    assert result == ["결과2"]


async def test_팩트와_시도가_다르면_따로_캐시된다():
    session = _FakeSession(version=20254)
    repo = AreaScorePgRepository(session=session)
    calls = []

    async def compute():
        calls.append(1)
        return len(calls)

    await repo._cached_city(("sales", "11"), _FakeOrm, compute)
    await repo._cached_city(("floating", "11"), _FakeOrm, compute)
    await repo._cached_city(("sales", "26"), _FakeOrm, compute)

    assert len(calls) == 3


async def test_서울_중앙값은_상권마다_재집계하지_않는다(monkeypatch):
    """점수 v2 벤치마크(시도 안 1,650곳 중앙값)는 상권과 무관하다 — 분기 버전 키로 한 번만 계산한다."""
    from market.adapter.outbound.pg.area_score_pg_repository import AreaScorePgRepository as R

    session = _FakeSession(version=20262)
    repo = R(session=session)
    computed = []

    async def fake_rows(self, *, trdar_code, sido_code):
        computed.append(sido_code)
        row = type("Row", (), dict(closure4=2.0, n4=4, sc0=10, amt=30_000_000, sal_sc=10, om=100.0))
        return 20262, [row, row]

    monkeypatch.setattr(R, "_score_input_rows", fake_rows)
    monkeypatch.setattr(R, "_latest_quarter", lambda self, orm: _async(20262))

    first = await repo.find_city_score_medians("11")
    second = await repo.find_city_score_medians("11")

    assert computed == ["11"], "두 번째 상권은 캐시에서 와야 한다"
    assert first == second
    assert first.closure_rate_4q == 2.0 and first.operating_months == 100.0 and first.sales_per_store_wan == 100.0


async def _async(value):
    return value


async def test_데이터가_없으면_캐시하지_않는다():
    # version이 None(빈 테이블)인데 캐시하면 적재 후에도 빈 값이 굳는다.
    session = _FakeSession(version=None)
    repo = AreaScorePgRepository(session=session)
    calls = []

    async def compute():
        calls.append(1)
        return []

    await repo._cached_city(("sales", "11", 5), _FakeOrm, compute)
    await repo._cached_city(("sales", "11", 5), _FakeOrm, compute)

    assert len(calls) == 2
    assert mod._CITY_CACHE == {}
