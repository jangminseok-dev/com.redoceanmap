from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from stock.app.dtos.forecast_refit_dto import RefitReportView, RefitRunResult
from stock.app.dtos.signal_config_dto import ConfigHistoryRow
from stock.app.ports.input.forecast_refit_use_case import ForecastRefitUseCase
from stock.app.ports.output.forecast_snapshot_repository import ForecastSnapshotRepositoryPort
from stock.app.ports.output.refit_report_repository import RefitReportRepositoryPort
from stock.app.ports.output.signal_config_port import SignalConfigPort
from stock.domain.entities.forecast_snapshot import ForecastSnapshot
from stock.domain.services import weight_refit
from stock.domain.services.weight_refit import RefitSample

logger = logging.getLogger(__name__)

GATE_HORIZON = 5             # 승격 판정 지평 — 20일은 참고 병기(표본 축적이 4배 느리다)
REFERENCE_HORIZONS = (5, 20)  # 스냅샷 배치와 동일한 지평 세트


class ForecastRefitInteractor(ForecastRefitUseCase):
    """가중치 재적합 대장 — 채점 표본 수집 → 도메인 재채점 → 게이트 통과 시 자동 승격.

    표본 규칙: 채점 완료 전량에서 `earnings_veto=True`만 제외한다(발표 구간은 기술
    신호가 무의미 — 백테스트 평가일 제외와 동일 취지). NULL 조합(2026-07-30 이전
    default() 시기) 표본은 **포함**한다 — 원신호는 config 무관하게 동결돼 있어
    제외하면 표본 절반을 유실한다. 저장된 `hit`은 재사용하지 않는다(옛 direction 기준).
    """

    def __init__(
        self,
        snapshots: ForecastSnapshotRepositoryPort,
        configs: SignalConfigPort,
        reports: RefitReportRepositoryPort,
    ) -> None:
        self._snapshots = snapshots
        self._configs = configs
        self._reports = reports

    async def run(self, promote: bool) -> RefitRunResult:
        samples_by_horizon: dict[int, list[RefitSample]] = {}
        for horizon in REFERENCE_HORIZONS:
            scored = await self._snapshots.find_scored_all(horizon)
            samples_by_horizon[horizon] = [self._sample(s) for s in scored if self._usable(s)]

        active = await self._configs.active()
        # 후보 32조합 × 표본 전량 재채점(CPU) — 이벤트 루프를 막지 않게 스레드로 분리
        report = await asyncio.to_thread(
            weight_refit.refit, samples_by_horizon, active.config, GATE_HORIZON
        )

        activated_key: str | None = None
        if promote and report.promote:
            activated_key = f"refit-{datetime.now(UTC):%Y%m%d}"  # 14자 — String(24) 내
            await self._configs.activate(activated_key, report.winner_config())

        await self._reports.save(
            params={
                "promote": promote,
                "gate_horizon": GATE_HORIZON,
                "horizons": list(REFERENCE_HORIZONS),
                "current_key": active.key,
                "activated_key": activated_key,
                "samples": {str(h): len(v) for h, v in samples_by_horizon.items()},
            },
            payload=report.to_payload(),
        )
        logger.info(
            "[forecast-refit] 표본 %s promote=%s → 승격 %s(%s) 사유 %s",
            {h: len(v) for h, v in samples_by_horizon.items()}, promote,
            activated_key is not None, activated_key, "; ".join(report.reasons),
        )
        return RefitRunResult(
            promoted=activated_key is not None,
            activated_key=activated_key,
            reasons=report.reasons,
        )

    async def latest(self) -> RefitReportView | None:
        return await self._reports.latest()

    async def config_history(self) -> list[ConfigHistoryRow]:
        return await self._configs.history()

    @staticmethod
    def _usable(s: ForecastSnapshot) -> bool:
        return s.realized_return_pct is not None and not s.earnings_veto

    @staticmethod
    def _sample(s: ForecastSnapshot) -> RefitSample:
        return RefitSample(
            signals={c.key: c.signal for c in s.signals},
            realized_return_pct=s.realized_return_pct,
            ticker=s.ticker,
            atr_pct=s.atr_pct,
            as_of=s.as_of,
        )
