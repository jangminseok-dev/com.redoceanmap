"""Gemini REST 클라이언트 — 오케스트레이터의 '외부 생성' 갈래.

2026-09-15 허브 어댑터(hub/adapter/outbound/gemini_api_adapter.py)에서 옮겨왔다. 프로젝트의
LLM 호출은 전부 오케스트레이터로 수렴한다는 원칙을 외부 API까지 적용하기 위해서다.
허브 포트(GeminiAnswerPort)는 그대로 두고 어댑터가 여기로 위임한다 — 스포크의 의존은 안 바뀐다.
"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class ExternalLLMError(Exception):
    """외부 LLM 호출 실패(키 미설정·HTTP 오류·빈 응답)."""


class GeminiClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self.model = model

    @property
    def ready(self) -> bool:
        return bool(self._api_key)

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        history: list[dict[str, str]] | None = None,
        json_mode: bool = False,
    ) -> str:
        if not self._api_key:
            raise ExternalLLMError("GEMINI_API_KEY가 설정되지 않았습니다 (루트 .env)")

        contents = [
            {"role": "model" if m["role"] == "assistant" else "user",
             "parts": [{"text": m["content"]}]}
            for m in (history or [])
        ]
        contents.append({"role": "user", "parts": [{"text": prompt}]})
        payload: dict = {"contents": contents}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            payload["generationConfig"] = {"responseMimeType": "application/json"}
        headers = {"x-goog-api-key": self._api_key}
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    _API_URL.format(model=self.model), json=payload, headers=headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ExternalLLMError(f"Gemini API 호출 실패: {exc}") from exc

        data = response.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ExternalLLMError(f"Gemini 응답 형식 오류: {str(data)[:200]}") from exc
        if not text:
            raise ExternalLLMError("Gemini가 빈 답변을 반환했습니다")
        logger.info("[gemini] %s → 답변 %d자", self.model, len(text))
        return text
