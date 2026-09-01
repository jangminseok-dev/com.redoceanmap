from __future__ import annotations

from hub.app.dtos.forecast_refit_dto import (
    RefitCandidateRow,
    RefitHorizonBoard,
    RefitReportInfo,
    RefitRunOutcome,
    SignalConfigInfo,
)
from hub.app.ports.output.forecast_refit_port import ForecastRefitPort
from stock.app.ports.input.forecast_refit_use_case import ForecastRefitUseCase


def _candidate(c: dict | None, board_baseline: float = 0.0) -> RefitCandidateRow | None:
    # payload 키는 weight_refit.RefitReport.to_payload()가 정의 —
    # 누락 키는 .get() 관용(구버전 리포트 공존, NewsEventStudyGateway 선례)
    if c is None:
        return None
    return RefitCandidateRow(
        up_threshold=c.get("up_threshold", 0.0),
        w_rsi=c.get("w_rsi", 0.0), w_trend=c.get("w_trend", 0.0),
        w_bb=c.get("w_bb", 0.0), w_obv=c.get("w_obv", 0.0),
        w_momentum=c.get("w_momentum", 0.0),
        n=c.get("n", 0), hits=c.get("hits", 0), hit_rate=c.get("hit_rate"),
        # 기준선은 행이 아니라 보드 레벨(baseline_up_rate)에 있다 — 행 payload에 baseline
        # 키가 없어 폴백 0.0이 그대로 소비돼 "기준선 0%"로 출력됐다(2026-09-01 실측 q05).
        # 같은 지평의 후보들은 기준선을 공유하므로 보드 값을 채운다.
        baseline=c.get("baseline", board_baseline),
        wilson_lower=c.get("wilson_lower", 0.0),
        is_current=c.get("is_current", False),
        gate_passed=c.get("gate_passed", False),
    )


class ForecastRefitGateway(ForecastRefitPort):
    """허브 ForecastRefitPort 구현 — 유스케이스 결과를 허브 계약 DTO로 변환해 위임."""

    def __init__(self, use_case: ForecastRefitUseCase) -> None:
        self._use_case = use_case

    async def run(self, promote: bool) -> RefitRunOutcome:
        result = await self._use_case.run(promote)
        return RefitRunOutcome(
            promoted=result.promoted,
            activated_key=result.activated_key,
            reasons=result.reasons,
        )

    async def latest(self) -> RefitReportInfo | None:
        view = await self._use_case.latest()
        if view is None:
            return None
        payload = view.payload or {}
        return RefitReportInfo(
            ran_at=view.ran_at,
            params=view.params or {},
            gate_horizon=payload.get("gate_horizon", 0),
            promote=payload.get("promote", False),
            # winner의 기준선은 게이트 판정 지평 보드의 것을 쓴다(같은 지평에서 뽑힌 승자)
            winner=_candidate(
                payload.get("winner"),
                next(
                    (b.get("baseline_up_rate", 0.0) for b in payload.get("boards", [])
                     if b.get("horizon_days") == payload.get("gate_horizon")),
                    0.0,
                ),
            ),
            reasons=payload.get("reasons", []),
            boards=[
                RefitHorizonBoard(
                    horizon_days=b.get("horizon_days", 0),
                    total=b.get("total", 0),
                    baseline_up_rate=b.get("baseline_up_rate", 0.0),
                    current=_candidate(b.get("current"), b.get("baseline_up_rate", 0.0)),
                    rows=[
                        _candidate(r, b.get("baseline_up_rate", 0.0))
                        for r in b.get("rows", [])
                    ],
                )
                for b in payload.get("boards", [])
            ],
        )

    async def config_history(self) -> list[SignalConfigInfo]:
        rows = await self._use_case.config_history()
        return [
            SignalConfigInfo(
                key=r.key, is_active=r.is_active, source=r.source,
                up_threshold=r.config.up_threshold, down_threshold=r.config.down_threshold,
                w_sentiment=r.config.w_sentiment, w_rsi=r.config.w_rsi,
                w_trend=r.config.w_trend, w_bb=r.config.w_bb,
                w_obv=r.config.w_obv, w_momentum=r.config.w_momentum,
                created_at=r.created_at, activated_at=r.activated_at,
            )
            for r in rows
        ]
