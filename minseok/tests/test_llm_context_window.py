"""컨텍스트 창 계약 — 서버 기본값에 맡기지 않는다.

2026-08-28 실장애 회귀 방지: Ollama 기본 num_ctx는 4,096인데 phase1 프롬프트가 4,178토큰이
되면서 **앞부분(JSON 형식 지시문)이 조용히 잘려** phase1의 코드 반환이 40/40 → 0/44로 죽었다.
결정론 지역 가드가 가려서 region_hit_rate는 1.0으로 보였고, 4일간 아무도 몰랐다.
"""
import asyncio

from core.llm.llm_orchestrator import NUM_CTX, LLMOrchestrator, ModelSpec


class _SpyClient:
    """ollama AsyncClient 대역 — 전달된 옵션만 기록한다."""

    def __init__(self) -> None:
        self.options: dict | None = None

    async def chat(self, **kwargs):
        self.options = kwargs.get("options")
        return {"message": {"content": "ok"}, "prompt_eval_count": 10}


def test_orchestrate는_num_ctx를_명시한다():
    spy = _SpyClient()
    orch = LLMOrchestrator()
    orch.register("test", ModelSpec(name="exaone3.5:7.8b", label="테스트"), default=True)
    orch._client = spy  # 러너(test_eval_runner)와 같은 기법 — 실호출 없이 옵션만 본다
    asyncio.run(orch.orchestrate("안녕"))
    assert spy.options == {"num_ctx": NUM_CTX}


def test_창은_phase1_실측_프롬프트보다_넉넉하다():
    # 사고 당시 phase1 프롬프트가 4,179토큰이었다. 여유 없이 딱 맞추면 표가 한 줄만 늘어도
    # 같은 사고가 재발한다 — 모델 자체는 32,768까지 지원한다.
    assert NUM_CTX >= 8192
