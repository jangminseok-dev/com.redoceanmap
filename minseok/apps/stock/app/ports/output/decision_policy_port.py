from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyOutput:
    raw: str
    model: str
    latency_ms: int


class DecisionPolicyPort(ABC):
    """LLM 판단 아웃바운드 포트 — 프롬프트를 주면 원문 응답을 돌려준다. 파싱은 도메인 몫."""

    @abstractmethod
    async def decide(self, system: str, prompt: str) -> PolicyOutput: ...
