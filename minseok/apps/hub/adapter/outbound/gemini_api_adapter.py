from __future__ import annotations

from core.llm.gemini_client import ExternalLLMError
from core.llm.llm_orchestrator import llm_orchestrator
from hub.app.dtos.gemini_dto import GeminiAnswerResponse
from hub.app.ports.output.gemini_answer_port import GeminiAnswerError, GeminiAnswerPort


class GeminiApiAdapter(GeminiAnswerPort):
    """허브 소유 외부 LLM 포트 구현 — 호출 자체는 오케스트레이터의 외부 생성 갈래로 위임한다
    (2026-09-15: REST 호출은 core/llm/gemini_client.py로 이동, 모든 LLM 호출의 단일 진입점 원칙)."""

    async def generate(self, prompt: str) -> GeminiAnswerResponse:
        try:
            text = await llm_orchestrator.orchestrate_external(prompt)
        except ExternalLLMError as exc:
            raise GeminiAnswerError(str(exc)) from exc
        return GeminiAnswerResponse(answer=text, model=llm_orchestrator.external_model_name or "")
