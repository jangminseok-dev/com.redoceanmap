from __future__ import annotations

import logging
import re

from core.llm.llm_orchestrator import llm_orchestrator
from stock.app.ports.output.sentiment_port import SentimentPort
from stock.domain.value_objects.sentiment_score import SentimentScore

logger = logging.getLogger(__name__)

_PROMPT = (
    "다음 뉴스 헤드라인들의 시장 감성을 -1.0(매우 부정) ~ 1.0(매우 긍정) 사이의 "
    "소수 하나로만 답하라. 설명 없이 숫자만 출력한다.\n\n헤드라인:\n{headlines}"
)


def _parse_score(raw: str) -> float:
    """응답의 -1~1 숫자 전부의 평균. 모델이 "소수 하나" 대신 헤드라인마다 한 줄씩 돌려주는 일이 잦은데
    (2026-09-21 로그 3건 중 2건), 첫 숫자만 읽으면 첫 헤드라인 하나의 점수가 종목 감성이 된다."""
    values = [v for v in (float(m) for m in re.findall(r"-?\d+(?:\.\d+)?", raw)) if -1.0 <= v <= 1.0]
    return sum(values) / len(values) if values else 0.0


class ExaoneSentimentAdapter(SentimentPort):
    """EXAONE(Ollama) 로 뉴스 감성을 점수화한다.

    대장이 LLM 추론이 필요할 때 위임하는 유일한 지점. 단일 모델(7.8B) 정책.
    """

    async def analyze(self, headlines: list[str]) -> SentimentScore:
        if not headlines:
            # 뉴스가 없으면(한국 종목 등) LLM을 부르지 않고 중립으로 둔다.
            return SentimentScore(value=0.0)
        prompt = _PROMPT.format(headlines="\n".join(f"- {h}" for h in headlines))
        # temperature 0 — 같은 헤드라인이면 같은 점수(샘플링 때문에 같은 종목이 1분 사이에 부호까지 바뀌었다)
        raw = await llm_orchestrator.orchestrate(prompt, options={"temperature": 0})
        score = _parse_score(raw)
        logger.info("[exaone-sentiment] raw=%r → %.2f", raw.strip()[:40], score)
        return SentimentScore(value=score)
