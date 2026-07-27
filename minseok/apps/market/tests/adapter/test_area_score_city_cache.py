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


async def test_분기수가_달라도_캐시를_공유한다(monkeypatch):
    """4/8/20분기를 오갈 때 캐시가 조각나면 안 된다 — 최대 창을 캐시하고 잘라 쓴다."""
    from market.adapter.outbound.pg.area_score_pg_repository import AreaScorePgRepository as R
    from market.domain.value_objects.area_score_vo import QuarterValue

    session = _FakeSession(version=20254)
    repo = R(session=session)
    computed = []

    async def fake_city_series(self, key, sido_code, fact_orm, value_col):
        async def compute():
            computed.append(1)
            return [QuarterValue(year_quarter=20211 + i, value=float(i)) for i in range(20)]

        return await self._cached_city((key, sido_code), _FakeOrm, compute)

    monkeypatch.setattr(R, "_city_series", fake_city_series)

    four = await repo.find_city_sales_series("11", 4)
    twenty = await repo.find_city_sales_series("11", 20)

    assert len(computed) == 1, "분기수가 달라도 집계는 한 번뿐이어야 한다"
    assert len(four) == 4 and len(twenty) == 20
    assert four == twenty[-4:], "짧은 창은 긴 창의 뒤쪽(최신)이어야 한다"


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
