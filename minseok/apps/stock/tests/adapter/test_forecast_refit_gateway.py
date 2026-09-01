"""ForecastRefitGateway 테스트 — payload 변환 규칙(기준선 채움)을 고정한다."""
from __future__ import annotations

from datetime import datetime, timezone

from stock.adapter.outbound.gateways.forecast_refit_gateway import ForecastRefitGateway

_NOW = datetime(2026, 9, 1, 6, 0, tzinfo=timezone.utc)


class _View:
    def __init__(self, payload: dict):
        self.ran_at = _NOW
        self.params = {}
        self.payload = payload


class _StubUseCase:
    def __init__(self, payload: dict):
        self._payload = payload

    async def latest(self):
        return _View(self._payload)


async def test_행에_baseline_키가_없으면_보드_기준선을_채운다():
    # 2026-09-01 실측 q05: 행 payload에 baseline 키가 없어 폴백 0.0이 "기준선 0%"로 출력됐다
    payload = {
        "gate_horizon": 5,
        "winner": {"n": 330, "hits": 216, "wilson_lower": 0.60},
        "boards": [{
            "horizon_days": 5,
            "total": 3301,
            "baseline_up_rate": 0.571,
            "current": {"n": 330, "hits": 216, "is_current": True},
            "rows": [{"n": 120, "hits": 83}],
        }],
    }
    report = await ForecastRefitGateway(use_case=_StubUseCase(payload)).latest()

    board = report.boards[0]
    assert board.current.baseline == 0.571
    assert board.rows[0].baseline == 0.571
    assert report.winner.baseline == 0.571  # 게이트 판정 지평 보드의 기준선


async def test_행에_baseline이_있으면_그대로_쓴다():  # 무손상 — 향후 행 단위 기준선 공존
    payload = {
        "gate_horizon": 5,
        "boards": [{
            "horizon_days": 5, "baseline_up_rate": 0.571,
            "rows": [{"n": 10, "baseline": 0.42}],
        }],
    }
    report = await ForecastRefitGateway(use_case=_StubUseCase(payload)).latest()
    assert report.boards[0].rows[0].baseline == 0.42
