from __future__ import annotations

import logging
import time

from core.llm.llm_orchestrator import llm_orchestrator
from stock.app.ports.output.decision_policy_port import DecisionPolicyPort, PolicyOutput

logger = logging.getLogger(__name__)


class ExaoneDecisionAdapter(DecisionPolicyPort):
    """EXAONE(오케스트레이터 경유)로 일일 매매 판단 원문을 받는다 — JSON 강제, temperature 0.

    파싱·검증은 도메인(`decision_parser`) 몫이고 여기서는 부르고 재기만 한다.
    """

    async def decide(self, system: str, prompt: str) -> PolicyOutput:
        started = time.monotonic()
        raw = await llm_orchestrator.orchestrate(prompt, system=system, format="json", options={"temperature": 0})
        latency = int((time.monotonic() - started) * 1000)
        logger.info("[paper] EXAONE 판단 %dms, %d자", latency, len(raw))
        return PolicyOutput(raw=raw, model=llm_orchestrator.default_model_name, latency_ms=latency)
