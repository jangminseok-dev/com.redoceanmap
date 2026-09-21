"""결론 한 줄 — 대표 입력을 `verdict_cases.json`으로 고정한다.

같은 픽스처를 프론트 `www/lib/verdict.ts`에도 돌려 두 구현이 같은 문장을 내는지 확인했다(2026-09-21 —
프론트에는 테스트 러너가 없어 일회성 node 스크립트로). 규칙을 바꾸면 이 픽스처와 verdict.ts를 함께 바꾼다.
"""
import json
from pathlib import Path

import pytest

from chat.domain.services.verdict import verdict
from hub.app.dtos.stock_forecast_dto import StockForecastSummary, StockRiskEvidence, StockRiskSummary

CASES = json.loads((Path(__file__).parent / "verdict_cases.json").read_text(encoding="utf-8"))


def _forecast(case: dict) -> StockForecastSummary | None:
    risk = case.get("risk")
    prob = case.get("probability") or {}
    if risk is None and not prob:
        return None
    return StockForecastSummary(
        signal_direction=case["direction"],
        risk=StockRiskSummary(
            vol_state=risk["vol_state"], drawdown_risk=risk["drawdown_risk"], rv_percentile=risk["rv_percentile"],
            evidence=tuple(StockRiskEvidence(**e) for e in risk["evidence"]),
        ) if risk else None,
        **prob,
    )


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_결론_문장(case):
    headline, detail = verdict(case["direction"], _forecast(case), case["score"], case["up_threshold"])
    assert headline == case["headline"]
    assert detail == case["detail"]


def test_중립_문장은_상쇄되지_않은_종목에_상쇄라고_말하지_않는다():
    """회귀 — 예전 문구는 점수가 뚜렷이 음수여도 "지표들이 서로 상쇄돼"라고 했다(중립의 74%에서 거짓)."""
    _, detail = verdict("NEUTRAL", None, -0.6, 0.35)
    assert "상쇄" not in detail


def test_점수_없이_불러도_동작한다():
    """구버전 호출(점수 미전달) — 방향 이유를 특정하지 않는 일반 문장으로 열화."""
    headline, detail = verdict("NEUTRAL", None)
    assert headline == "지금은 방향을 말하기 어렵습니다"
    assert detail == "방향은 과거 검증에서 평소와 구별되지 않아 말하지 않아요."
