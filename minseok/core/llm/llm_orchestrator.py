"""LLM 오케스트레이터 — 프로젝트의 모든 LLM 호출이 수렴하는 단일 진입점.

세 갈래를 분기한다(2026-09-15 역할 확정 — 그 전까지는 이름만 오케스트레이터였고 실제로는
로컬 모델 하나의 게이트웨이였다):

1. **로컬 생성** — Ollama의 기본 생성 모델(`LLM_MODEL`, 2026-09-15부터 Gemma 4 e4b QAT).
   의도 분류·도메인 추론·최종 답변·감성·모의투자 판단·요약 전부. 사고(thinking) 모드는
   env 기본(`LLM_THINK`)에 호출 단위 `think=` 인자로 덮어쓴다 — 지연이 무관한 배치 판단은
   켜고 대화는 끈다.
2. **임베딩** — Ollama의 임베딩 모델(`EMBED_MODEL`, 2026-09-15부터 embeddinggemma 768차원).
   질의와 문서에 모델별 프롬프트를 붙인다(embeddinggemma·e5 계열은 프롬프트 유무로 품질이 갈린다).
3. **외부 생성** — Gemini API. 상권·주식과 무관한 일반 질문(허브 GeminiAnswerPort 경유)과,
   `LLM_FALLBACK=external`일 때 Ollama 장애(접속 불가·5xx)의 폴백.

단일 모델 정책(2026-07-15 → 2026-09-15 개정): "생성 모델 하나 + 임베딩 모델 하나 + 외부 폴백".
생성 모델을 여러 개 동시에 두지 않는다 — 8GB VRAM과 프롬프트 튜닝 일관성 때문이다.
교체 절차: ollama pull → `.env`의 LLM_MODEL/EMBED_MODEL 교체 → 골든셋 게이트(chat 134문항·검색 40+20문항)
→ baseline 재박제. 상세 `_docs/LLM_SWAP_EVAL_2026-09-14.md`.

core.config가 아니라 관리자를 직접 쓰는 이유: 이 모듈은 DATABASE_URL 없는 환경
(학습·연구 스크립트)에서도 import돼야 한다 — core.config는 그 키를 필수로 요구한다.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

import httpx
from ollama import AsyncClient, ResponseError

from core.key.secret_manager import get_secret_manager
from core.llm.gemini_client import ExternalLLMError, GeminiClient

logger = logging.getLogger(__name__)

# 컨텍스트 창 — **앱 계약으로 명시한다**(서버 기본값에 맡기지 않는다).
# 2026-08-28 실장애: 기본값이 4,096인데 phase1 프롬프트가 4,042→4,178토큰으로 커지자
# Ollama가 **앞부분을 조용히 버려** JSON 형식 지시문이 통째로 날아갔다. 모델에는 상권 표만
# 남아 표를 그대로 옮겨 적었고, phase1의 코드 반환이 40/40 → 0/44로 죽었다. 결정론 지역
# 가드가 이를 가려 region_hit_rate는 1.0으로 보였다 — 지표로는 안 잡히는 종류의 붕괴다.
# 8,192는 여유를 두되 KV 캐시(≈1GB)로 VRAM을 더 쓰는 값이다.
NUM_CTX = 8192
# 이 비율을 넘으면 경고 — 잘리기 전에 알아야 한다(잘린 뒤에는 조용하다)
_CONTEXT_WARN_RATIO = 0.9

# 임베딩 프롬프트 — 모델 태그 부분 문자열 → (질의 접두, 문서 접두). 골든셋 풀 재순위 실측(2026-09-15)
# 에서 embeddinggemma는 이 프롬프트를 붙였을 때의 값(뉴스 nDCG@5 0.902)이다. 없는 모델은 접두 없음.
_EMBED_PROMPTS: dict[str, tuple[str, str]] = {
    "embeddinggemma": ("task: search result | query: ", "title: none | text: "),
    "e5": ("query: ", "passage: "),
}


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


def _is_local_outage(exc: Exception) -> bool:
    """Ollama가 죽었거나(접속 불가) 서버 오류(5xx)인 경우만 폴백 대상 — 4xx(프롬프트·모델 문제)는 아니다."""
    if isinstance(exc, httpx.TransportError):
        return True
    return isinstance(exc, ResponseError) and (exc.status_code or 0) >= 500


class LLMOrchestrator:
    """로컬 생성 · 임베딩 · 외부 생성 세 갈래를 가진 오케스트레이터(인스턴스는 하나)."""

    def __init__(
        self,
        *,
        gen_model: str,
        embed_model: str,
        think: bool | None,
        keep_alive: str,
        external: GeminiClient | None,
        fallback_external: bool,
        host: str | None = None,
    ) -> None:
        self._client = AsyncClient(host=host) if host else AsyncClient()
        self._gen_model = gen_model
        self._embed_model = embed_model
        self._think = think
        self._keep_alive = keep_alive
        self._external = external
        self._fallback = fallback_external and external is not None and external.ready
        prompts = next((p for key, p in _EMBED_PROMPTS.items() if key in embed_model), ("", ""))
        self._query_prefix, self._doc_prefix = prompts

    # --- 식별 ---
    @property
    def default_model_name(self) -> str:
        return self._gen_model

    @property
    def embed_model_name(self) -> str:
        return self._embed_model

    @property
    def external_model_name(self) -> str | None:
        return self._external.model if self._external else None

    # --- 내부 ---
    @staticmethod
    def _build_messages(
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

    def _think_kwargs(self, think: bool | None) -> dict:
        resolved = self._think if think is None else think
        return {} if resolved is None else {"think": resolved}

    # --- 1. 로컬 생성 ---
    async def orchestrate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system: str | None = None,
        history: list[dict[str, str]] | None = None,
        format: str | None = None,
        options: dict | None = None,
        think: bool | None = None,
    ) -> str:
        """프롬프트를 추론한다. model 미지정이면 기본 생성 모델. system/history로 멀티턴 지원.
        format="json"이면 유효 JSON 출력을 강제한다. options는 Ollama 옵션 추가분
        (예: {"temperature": 0} — 재현성이 필요한 배치 판단). think는 사고 모드 호출 단위 덮어쓰기.
        Ollama 장애 시 `LLM_FALLBACK=external`이면 같은 프롬프트를 외부 생성으로 보낸다."""
        kwargs: dict = {}
        if format:
            kwargs["format"] = format
        try:
            response = await self._client.chat(
                model=model or self._gen_model,
                messages=self._build_messages(prompt, system, history),
                options={"num_ctx": NUM_CTX, **(options or {})},
                keep_alive=self._keep_alive,
                **self._think_kwargs(think),
                **kwargs,
            )
        except Exception as exc:
            if not (self._fallback and _is_local_outage(exc)):
                raise
            logger.warning("[llm] 로컬 생성 장애(%s) → 외부 생성 폴백", type(exc).__name__)
            return await self.orchestrate_external(
                prompt, system=system, history=history, format=format,
            )
        _warn_if_near_context(response.get("prompt_eval_count"))
        return response["message"]["content"]

    async def orchestrate_stream(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system: str | None = None,
        history: list[dict[str, str]] | None = None,
        think: bool | None = None,
    ) -> AsyncGenerator[str, None]:
        """orchestrate와 동일하되 응답을 토큰 단위로 스트리밍한다(대화형 UX용). 폴백은 없다 —
        외부 API는 스트리밍 계약이 달라 호출부가 orchestrate로 내려가는 편이 낫다."""
        stream = await self._client.chat(
            model=model or self._gen_model,
            messages=self._build_messages(prompt, system, history),
            options={"num_ctx": NUM_CTX},
            stream=True,
            keep_alive=self._keep_alive,
            **self._think_kwargs(think),
        )
        async for part in stream:
            if part.get("done"):
                _warn_if_near_context(part.get("prompt_eval_count"))
            chunk = part["message"]["content"]
            if chunk:
                yield chunk

    # --- 2. 임베딩 ---
    async def embed(self, text: str, *, kind: str = "query") -> list[float]:
        """단건 임베딩(pgvector 저장·검색용). kind는 "query"(검색 질의) 또는 "document"(적재 문서) —
        프롬프트를 쓰는 모델은 둘을 구분해야 저장 벡터와 질의 벡터가 같은 공간에 놓인다."""
        prefix = self._doc_prefix if kind == "document" else self._query_prefix
        response = await self._client.embed(
            model=self._embed_model, input=prefix + text, keep_alive=self._keep_alive,
        )
        return list(response["embeddings"][0])

    async def embed_many(self, texts: list[str], *, kind: str = "document") -> list[list[float]]:
        """배치 임베딩 — 여러 텍스트를 HTTP 1콜로 처리한다(수집 주기 지연 최소화). 기본은 문서."""
        prefix = self._doc_prefix if kind == "document" else self._query_prefix
        response = await self._client.embed(
            model=self._embed_model, input=[prefix + t for t in texts], keep_alive=self._keep_alive,
        )
        return [list(e) for e in response["embeddings"]]

    # --- 3. 외부 생성 ---
    async def orchestrate_external(
        self,
        prompt: str,
        *,
        system: str | None = None,
        history: list[dict[str, str]] | None = None,
        format: str | None = None,
    ) -> str:
        """외부 생성(Gemini). 실패는 ExternalLLMError."""
        if self._external is None:
            raise ExternalLLMError("외부 생성 모델이 구성되지 않았습니다")
        return await self._external.generate(
            prompt, system=system, history=history, json_mode=(format == "json"),
        )


# --- 인스턴스는 하나. 갈래별 모델은 env가 정한다(모듈 docstring 참고). ---
_secrets = get_secret_manager()
_MODEL_TAG = _secrets.get("LLM_MODEL", "gemma4:e4b-it-qat")
_EMBED_TAG = _secrets.get("EMBED_MODEL", "embeddinggemma")
# 사고(thinking) 모드 기본값(③-M5② 2026-09-14 실측): Gemma 4 계열은 Ollama 기본이 사고 모드 켜짐이라
# 답변당 수십 초가 걸리고 사고 토큰이 출력 예산을 잠식한다. "off"면 think=False, "on"이면 think=True,
# 비우면 서버 기본(모델별)에 맡긴다. 비사고 모델에 think=False를 넘겨도 Ollama는 오류 없이 무시한다.
THINK: bool | None = {"off": False, "on": True}.get(_secrets.get("LLM_THINK", "off").strip().lower())
# 모델 상주 시간(2026-09-15): Ollama 기본 keep_alive 5분이면 유휴 뒤 첫 질문에 10~20초 콜드 로드가 붙는다.
# 백엔드 PC는 sudo 없이 systemd 오버라이드를 못 바꾸므로 요청마다 넘긴다. 생성·임베딩 둘 다.
KEEP_ALIVE = _secrets.get("LLM_KEEP_ALIVE", "24h").strip() or "24h"
# 외부 폴백 — 평가 러너는 off로 돌린다(로컬 모델 품질을 재는 자리에 외부 답이 섞이면 안 된다).
FALLBACK_EXTERNAL = _secrets.get("LLM_FALLBACK", "off").strip().lower() == "external"

llm_orchestrator = LLMOrchestrator(
    gen_model=_MODEL_TAG,
    embed_model=_EMBED_TAG,
    think=THINK,
    keep_alive=KEEP_ALIVE,
    external=GeminiClient(_secrets.get_gemini_api_key(), _secrets.get_gemini_model_name()),
    fallback_external=FALLBACK_EXTERNAL,
)


if __name__ == "__main__":
    import asyncio

    answer = asyncio.run(llm_orchestrator.orchestrate("한국어로 짧게 자기소개 해줘."))
    print(answer)
