"""컨텍스트 창 계약 — 서버 기본값에 맡기지 않는다.

2026-08-28 실장애 회귀 방지: Ollama 기본 num_ctx는 4,096인데 phase1 프롬프트가 4,178토큰이
되면서 **앞부분(JSON 형식 지시문)이 조용히 잘려** phase1의 코드 반환이 40/40 → 0/44로 죽었다.
결정론 지역 가드가 가려서 region_hit_rate는 1.0으로 보였고, 4일간 아무도 몰랐다.
"""
import asyncio

import httpx
import pytest

from core.llm.gemini_client import ExternalLLMError
from core.llm.llm_orchestrator import NUM_CTX, LLMOrchestrator


class _SpyClient:
    """ollama AsyncClient 대역 — 전달된 인자만 기록한다."""

    def __init__(self, fail: Exception | None = None) -> None:
        self.chat_kwargs: dict | None = None
        self.embed_kwargs: dict | None = None
        self._fail = fail

    async def chat(self, **kwargs):
        self.chat_kwargs = kwargs
        if self._fail:
            raise self._fail
        return {"message": {"content": "ok"}, "prompt_eval_count": 10}

    async def embed(self, **kwargs):
        self.embed_kwargs = kwargs
        return {"embeddings": [[0.1, 0.2] for _ in (kwargs["input"] if isinstance(kwargs["input"], list) else [0])]}


class _SpyExternal:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.model = "gemini-test"

    @property
    def ready(self) -> bool:
        return True

    async def generate(self, prompt, *, system=None, history=None, json_mode=False):
        self.calls.append({"prompt": prompt, "json": json_mode})
        return "외부 답"


def _orch(*, fail=None, external=None, fallback=False, embed_model="embeddinggemma", think=False):
    orch = LLMOrchestrator(
        gen_model="gemma4:test", embed_model=embed_model, think=think, keep_alive="24h",
        external=external, fallback_external=fallback,
    )
    orch._client = _SpyClient(fail)  # 러너(test_eval_runner)와 같은 기법 — 실호출 없이 인자만 본다
    return orch


def test_orchestrate는_num_ctx를_명시한다():
    orch = _orch()
    asyncio.run(orch.orchestrate("안녕"))
    assert orch._client.chat_kwargs["options"] == {"num_ctx": NUM_CTX}


def test_창은_phase1_실측_프롬프트보다_넉넉하다():
    # 사고 당시 phase1 프롬프트가 4,179토큰이었다. 여유 없이 딱 맞추면 표가 한 줄만 늘어도
    # 같은 사고가 재발한다 — 모델 자체는 32,768까지 지원한다.
    assert NUM_CTX >= 8192


def test_사고_모드는_env_기본에_호출_단위로_덮어쓴다():
    orch = _orch(think=False)
    asyncio.run(orch.orchestrate("a"))
    assert orch._client.chat_kwargs["think"] is False
    asyncio.run(orch.orchestrate("a", think=True))
    assert orch._client.chat_kwargs["think"] is True


def test_임베딩은_질의와_문서에_모델별_프롬프트를_붙인다():
    orch = _orch(embed_model="embeddinggemma")
    asyncio.run(orch.embed("삼성전자"))
    assert orch._client.embed_kwargs["input"] == "task: search result | query: 삼성전자"
    asyncio.run(orch.embed_many(["제목"]))
    assert orch._client.embed_kwargs["input"] == ["title: none | text: 제목"]
    # 프롬프트가 없는 모델(bge-m3 등)은 원문 그대로
    orch2 = _orch(embed_model="bge-m3")
    asyncio.run(orch2.embed("삼성전자"))
    assert orch2._client.embed_kwargs["input"] == "삼성전자"


def test_로컬_장애는_옵트인일_때만_외부로_폴백한다():
    outage = httpx.ConnectError("connection refused")
    ext = _SpyExternal()
    orch = _orch(fail=outage, external=ext, fallback=True)
    assert asyncio.run(orch.orchestrate("q", format="json")) == "외부 답"
    assert ext.calls == [{"prompt": "q", "json": True}]
    # 옵트인이 아니면 예외 그대로
    orch_off = _orch(fail=outage, external=ext, fallback=False)
    with pytest.raises(httpx.ConnectError):
        asyncio.run(orch_off.orchestrate("q"))


def test_프롬프트_문제_4xx는_폴백하지_않는다():
    from ollama import ResponseError
    ext = _SpyExternal()
    orch = _orch(fail=ResponseError("bad request", 400), external=ext, fallback=True)
    with pytest.raises(ResponseError):
        asyncio.run(orch.orchestrate("q"))
    assert ext.calls == []


def test_외부_생성_미구성이면_계약_예외():
    orch = _orch(external=None)
    with pytest.raises(ExternalLLMError):
        asyncio.run(orch.orchestrate_external("q"))
