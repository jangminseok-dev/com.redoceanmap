"""상권 요약 캐시 — chat이 상권 질문마다 전 상권(1,650) 조인을 재집계하지 않는다.

시도 벤치마크 캐시(test_area_score_city_cache)와 같은 방식: 최신 분기가 버전 키,
분기 적재 때만 자연 갱신. 세션 대역은 버전 조회(max)와 본계산(조인·매출 집계)을 구분해
호출 횟수로 캐시 히트를 검증한다.
"""
import pytest

from market.adapter.outbound.gateways import commercial_data_gateway as mod
from market.adapter.outbound.gateways.commercial_data_gateway import CommercialDataGateway


class _FakeResult:
    def __init__(self, scalar=None, rows=()):
        self._scalar = scalar
        self._rows = rows

    def scalar(self):
        return self._scalar

    def all(self):
        return list(self._rows)


class _FakeSession:
    def __init__(self, version):
        self.version = version
        self.version_calls = 0
        self.compute_calls = 0

    async def execute(self, stmt):
        if "max(" in str(stmt).lower():
            self.version_calls += 1
            return _FakeResult(scalar=self.version)
        self.compute_calls += 1
        return _FakeResult(rows=[])


@pytest.fixture(autouse=True)
def _clear_cache():
    mod._SUMMARY_CACHE.clear()
    yield
    mod._SUMMARY_CACHE.clear()


async def test_같은_분기면_재집계하지_않는다():
    session = _FakeSession(version=20261)
    gateway = CommercialDataGateway(session=session)
    first = await gateway.get_area_summary()
    computes_after_first = session.compute_calls
    second = await gateway.get_area_summary()
    assert second is first                     # 캐시 히트 — 같은 객체
    assert session.compute_calls == computes_after_first  # 본계산 추가 없음
    assert session.version_calls == 2          # 버전 키 조회만 매번


async def test_분기가_바뀌면_재집계한다():
    session = _FakeSession(version=20261)
    gateway = CommercialDataGateway(session=session)
    await gateway.get_area_summary()
    before = session.compute_calls
    session.version = 20262                    # 새 분기 적재 시뮬레이션
    await gateway.get_area_summary()
    assert session.compute_calls > before      # 자연 갱신


async def test_데이터_없는_상태는_캐시하지_않는다():
    session = _FakeSession(version=None)
    gateway = CommercialDataGateway(session=session)
    await gateway.get_area_summary()
    assert mod._SUMMARY_CACHE == {}            # 적재 후 첫 호출이 빈 캐시에 막히지 않게
