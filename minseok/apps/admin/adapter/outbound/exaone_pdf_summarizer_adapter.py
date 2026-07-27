"""추출 텍스트를 EXAONE 7.8B로 요약하는 어댑터.

LLM 추론 수렴 규칙에 따라 Ollama를 직접 부르지 않고 오케스트레이터를 경유한다.
길이 정책: 모델 컨텍스트를 넘기지 않도록 앞부분 MAX_INPUT_CHARS만 넣는 단발 요약이다
(청크 맵-리듀스는 호출이 N+1회로 늘어 업로드 응답이 분 단위가 되므로 채택하지 않았다).
잘린 경우 요약 말미에 그 사실을 명시해 "문서 전체 요약"으로 오해되지 않게 한다.
"""
from __future__ import annotations

from admin.app.ports.output.pdf_summarizer_port import PdfSummarizerPort
from core.llm.llm_orchestrator import llm_orchestrator

MAX_INPUT_CHARS = 6000

_SUMMARY_SYSTEM = """너는 문서 요약가다. 제공된 [본문]에만 근거해 한국어로 요약하라.
본문에 없는 내용을 추측하거나 외부 지식으로 채우지 마라.

출력 형식:
1) 3~5문장의 개요
2) '핵심 항목' 제목 아래 불릿 3~7개 (각 한 줄)

다른 머리말·맺음말은 붙이지 마라."""


class ExaonePdfSummarizerAdapter(PdfSummarizerPort):
    """PdfSummarizerPort의 LLM 오케스트레이터 구현(기본 모델 = EXAONE 7.8B)."""

    async def summarize(self, title: str, text: str) -> str:
        body = text[:MAX_INPUT_CHARS]
        truncated = len(text) > MAX_INPUT_CHARS
        prompt = f"[제목]\n{title}\n\n[본문]\n{body}"
        summary = (await llm_orchestrator.orchestrate(prompt, system=_SUMMARY_SYSTEM)).strip()
        if truncated:
            summary += (
                f"\n\n(※ 본문 {len(text):,}자 중 앞 {MAX_INPUT_CHARS:,}자만 요약한 결과입니다.)"
            )
        return summary
