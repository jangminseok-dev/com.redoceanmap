"""LLM 오케스트레이터.

등록된 LLM 모델 중 하나를 선택해 추론을 수행하는 중앙 LLM 오케스트레이터.
단일 모델 정책(2026-07-15): 오케스트레이터는 기본 모델 **하나만** 보유하며,
의도 분류·도메인 내부 추론·최종 사용자 답변이 전부 이 모델로 수행된다.
시스템 전체에 인스턴스는 하나(llm_orchestrator)이며, LLM 추론이 필요한
모든 지점이 이 오케스트레이터로 수렴한다.

③-M5(2026-08-23): 기본 모델 태그는 `LLM_MODEL` env로 갈아끼운다 — '동시 보유'가 아니라
'교체' 스위치다(단일 모델 정책 유지). 미설정 기본은 EXAONE 3.5 7.8B.
⚠ EXAONE 3.5는 NC 라이선스(연구 전용 — E5 실사 2026-08-17). 공개 서비스 전 상용 가능
모델(Llama 3.x·Gemma 3·카카오 Kanana — 중국 모델·중국 베이스 파인튜닝 배제)로 교체 필수.
교체 절차: ollama pull → `.env`의 LLM_MODEL 교체 → chat 품질 회귀(eval 하네스 120문항,
`LLM_MODEL=<후보>`로 러너 재실행 → test_quality_gate baseline 대조)로 판정 후 확정.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from ollama import AsyncClient

logger = logging.getLogger(__name__)

# 컨텍스트 창 — **앱 계약으로 명시한다**(서버 기본값에 맡기지 않는다).
# 2026-08-28 실장애: 기본값이 4,096인데 phase1 프롬프트가 4,042→4,178토큰으로 커지자
# Ollama가 **앞부분을 조용히 버려** JSON 형식 지시문이 통째로 날아갔다. 모델에는 상권 표만
# 남아 표를 그대로 옮겨 적었고, phase1의 코드 반환이 40/40 → 0/44로 죽었다. 결정론 지역
# 가드가 이를 가려 region_hit_rate는 1.0으로 보였다 — 지표로는 안 잡히는 종류의 붕괴다.
# 모델 자체는 32,768까지 지원한다. 8,192는 여유를 두되 KV 캐시(≈1GB)로 VRAM을 더 쓰는 값이다.
NUM_CTX = 8192
# 이 비율을 넘으면 경고 — 잘리기 전에 알아야 한다(잘린 뒤에는 조용하다)
_CONTEXT_WARN_RATIO = 0.9


def _warn_if_near_context(prompt_eval_count: int | None) -> None:
    """서버가 센 실제 프롬프트 토큰이 창에 근접하면 남긴다.

    사전 추정(글자수÷n)은 한국어에서 신뢰할 수 없어 **서버 카운트**를 쓴다. 사후지만
    조용한 절단보다 낫다 — 이 로그가 없어서 4일간 프로덕션이 깨진 줄 몰랐다.
    """
    if prompt_eval_count and prompt_eval_count >= NUM_CTX * _CONTEXT_WARN_RATIO:
        logger.warning(
            "[llm] 프롬프트 %d토큰 — 컨텍스트 창 %d의 %.0f%% 이상. 초과분은 앞에서 잘린다",
            prompt_eval_count, NUM_CTX, _CONTEXT_WARN_RATIO * 100,
        )


@dataclass(frozen=True)
class ModelSpec:
    """오케스트레이터에 등록되는 모델 명세."""

    name: str   # Ollama 모델 태그 (예: "exaone3.5:7.8b")
    label: str  # 사람이 읽는 이름


class LLMOrchestrator:
    """등록된 모델 중 하나를 골라 채팅 추론을 수행하는 오케스트레이터."""

    def __init__(self, host: str | None = None) -> None:
        self._client = AsyncClient(host=host) if host else AsyncClient()
        self._registry: dict[str, ModelSpec] = {}
        self._default: str | None = None

    def register(self, key: str, spec: ModelSpec, *, default: bool = False) -> None:
        """모델을 레지스트리에 등록한다. 첫 등록 모델은 자동으로 기본값이 된다."""
        self._registry[key] = spec
        if default or self._default is None:
            self._default = key

    @property
    def default_model_name(self) -> str:
        return self._resolve_model(None)

    def _resolve_model(self, model: str | None) -> str:
        if model is None:
            if self._default is None:
                raise RuntimeError("등록된 모델이 없습니다. register()로 먼저 등록하세요.")
            model = self._registry[self._default].name
        return model

    def _build_messages(
        self,
        prompt: str,
        system: str | None,
        history: list[dict[str, str]] | None,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        if history:
            messages.extend(history)  # [{"role": "user"|"assistant", "content": ...}]
        messages.append({"role": "user", "content": prompt})
        return messages

    async def orchestrate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system: str | None = None,
        history: list[dict[str, str]] | None = None,
        format: str | None = None,
        options: dict | None = None,
    ) -> str:
        """프롬프트를 추론한다. model 미지정이면 기본 모델(EXAONE 7.8B — 단일 모델 정책).
        system/history로 멀티턴 지원. format="json"이면 유효 JSON 출력을 강제한다.
        options는 Ollama 옵션 추가분(예: {"temperature": 0} — 재현성이 필요한 배치 판단)."""
        kwargs: dict = {}
        if format:
            kwargs["format"] = format
        response = await self._client.chat(
            model=self._resolve_model(model),
            messages=self._build_messages(prompt, system, history),
            options={"num_ctx": NUM_CTX, **(options or {})},
            **kwargs,
        )
        _warn_if_near_context(response.get("prompt_eval_count"))
        return response["message"]["content"]

    async def embed(self, text: str, *, model: str = "bge-m3") -> list[float]:
        """텍스트 임베딩(pgvector 저장·검색용). 채팅과 동일하게 오케스트레이터로 수렴한다."""
        response = await self._client.embed(model=model, input=text)
        return list(response["embeddings"][0])

    async def embed_many(self, texts: list[str], *, model: str = "bge-m3") -> list[list[float]]:
        """배치 임베딩 — 여러 텍스트를 HTTP 1콜로 처리한다(수집 주기 지연 최소화)."""
        response = await self._client.embed(model=model, input=texts)
        return [list(e) for e in response["embeddings"]]

    async def orchestrate_stream(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncGenerator[str, None]:
        """orchestrate와 동일하되 응답을 토큰 단위로 스트리밍한다(대화형 UX용)."""
        stream = await self._client.chat(
            model=self._resolve_model(model),
            messages=self._build_messages(prompt, system, history),
            options={"num_ctx": NUM_CTX},
            stream=True,
        )
        async for part in stream:
            if part.get("done"):
                _warn_if_near_context(part.get("prompt_eval_count"))
            chunk = part["message"]["content"]
            if chunk:
                yield chunk


# --- LLM 오케스트레이터는 하나. 기본 모델도 하나만 보유한다(단일 모델 정책). ---
# 태그는 LLM_MODEL env가 정한다(③-M5 교체 스위치 — 모듈 docstring 참고).
# core.config가 아니라 관리자를 직접 쓰는 이유: 이 모듈은 DATABASE_URL 없는 환경
# (학습·연구 스크립트)에서도 import돼야 한다 — core.config는 그 키를 필수로 요구한다.
from core.key.secret_manager import get_secret_manager

_MODEL_TAG = get_secret_manager().get("LLM_MODEL", "exaone3.5:7.8b")
DEFAULT_MODEL = ModelSpec(name=_MODEL_TAG, label=f"기본 모델 ({_MODEL_TAG})")

llm_orchestrator = LLMOrchestrator()
llm_orchestrator.register("default", DEFAULT_MODEL, default=True)


if __name__ == "__main__":
    import asyncio

    answer = asyncio.run(llm_orchestrator.orchestrate("한국어로 짧게 자기소개 해줘."))
    print(answer)
