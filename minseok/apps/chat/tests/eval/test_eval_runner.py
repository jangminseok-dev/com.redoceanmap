"""평가 러너 — 골든셋 134문항을 실제 기본 LLM(LLM_MODEL, 2026-09-15부터 Gemma 4 e4b)로 돌려 trace.jsonl을 만든다.

프로덕션 코드는 건드리지 않는다: 기존 test_chat_interactor와 같은 기법으로
모듈 네임스페이스의 llm_orchestrator를 "진짜 호출 + 기록" 프록시로 갈아끼운다.
phase 식별은 프롬프트 접두사(INTENT/PHASE1/PHASE2/답변 프롬프트)로 확정한다.

실행(백엔드 PC — ollama에 LLM_MODEL 모델 필요, DB는 불필요, LLM_FALLBACK은 off):
  docker run --rm --network host \
    -v /home/host/projects/com.redoceanmap:/work -w /work \
    -e PYTHONPATH=/work/minseok:/work/minseok/apps \
    minseok97/redoceanmap-backend:latest \
    python -m pytest minseok/apps/chat/tests/eval/test_eval_runner.py \
      -q -p no:cacheprovider -m ollama
"""
from __future__ import annotations

import json
import os
import re
import socket
import time
from urllib.parse import urlparse

import pytest

from chat.app.use_cases import chat_interactor as ci_module
from chat.app.use_cases.chat_interactor import ChatInteractor
from chat.domain.value_objects.eval_trace import CaseTrace, LlmCall
from chat.tests.eval.golden import TRACE_PATH, load_cases
from chat.tests.eval.snapshot_stubs import (
    SnapshotConversations,
    SnapshotFinance,
    SnapshotForecast,
    SnapshotFundamentals,
    SnapshotGemini,
    SnapshotMarket,
    SnapshotMarketNews,
    SnapshotNewsSearch,
    SnapshotRecorder,
    SnapshotStocks,
    seeded_conversations,
)
from core.llm.llm_orchestrator import llm_orchestrator

_PHASE_PREFIXES = (
    ("phase0", ci_module.INTENT_PROMPT[:40]),
    ("phase1", ci_module.PHASE1_PROMPT[:40]),
    ("phase2", ci_module.PHASE2_PROMPT[:40]),
    ("stock_answer", ci_module.STOCK_ANSWER_PROMPT[:40]),
    ("market_news_answer", ci_module.MARKET_NEWS_ANSWER_PROMPT[:40]),
)


def _phase_of(prompt: str) -> str:
    for phase, prefix in _PHASE_PREFIXES:
        if prompt.startswith(prefix):
            return phase
    return "unknown"


class _RecordingOrchestrator:
    """진짜 오케스트레이터를 감싸 phase·프롬프트·응답·지연을 기록한다."""

    def __init__(self) -> None:
        self.calls: list[LlmCall] = []

    async def orchestrate(self, prompt: str, **kwargs) -> str:
        start = time.perf_counter()
        response = await llm_orchestrator.orchestrate(prompt, **kwargs)
        self.calls.append(LlmCall(
            phase=_phase_of(prompt), prompt=prompt, response=response,
            latency_ms=(time.perf_counter() - start) * 1000,
        ))
        return response


def _phase1_raw_codes(calls: list[LlmCall]) -> tuple[int, ...]:
    for call in calls:
        if call.phase == "phase1":
            try:
                raw = call.response.strip()
                match = re.search(r"\{.*\}", raw, re.DOTALL)
                parsed = json.loads(re.sub(r",(\s*[}\]])", r"\1",
                                           match.group() if match else raw))
                return tuple(int(c) for c in parsed.get("trdar_codes", [])
                             if str(c).isdigit())
            except Exception:
                return ()
    return ()


def _ollama_reachable() -> bool:
    """OLLAMA_HOST(도커 → 호스트 ollama는 http://host.docker.internal:11434)를 존중한다.

    ollama 파이썬 클라이언트도 같은 환경 변수를 읽으므로 체크와 실제 접속이 일치한다.
    """
    host_env = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    parsed = urlparse(host_env if "//" in host_env else f"http://{host_env}")
    try:
        with socket.create_connection(
            (parsed.hostname or "127.0.0.1", parsed.port or 11434), timeout=2,
        ):
            return True
    except OSError:
        return False


@pytest.mark.ollama
async def test_run_eval_and_write_trace(monkeypatch):
    if not _ollama_reachable():
        pytest.skip("ollama(127.0.0.1:11434) 미가동 — 백엔드 PC에서 실행")

    cases = load_cases()
    traces: list[CaseTrace] = []
    for case in cases:
        market = SnapshotMarket()
        stocks, news = SnapshotStocks(), SnapshotNewsSearch()
        gemini = SnapshotGemini()
        seeded: tuple[int, ...] = ()
        if case.category == "multiturn":
            conversations, seeded = seeded_conversations(market, case.history_regions)
        else:
            conversations = SnapshotConversations()

        recorder = _RecordingOrchestrator()
        monkeypatch.setattr(ci_module, "llm_orchestrator", recorder)
        interactor = ChatInteractor(
            market=market, recorder=SnapshotRecorder(), conversations=conversations,
            stocks=stocks, news=news, market_news=SnapshotMarketNews(), gemini=gemini,
            forecaster=SnapshotForecast(), fundamentals=SnapshotFundamentals(),
            finance=SnapshotFinance(),
        )

        error: str | None = None
        answer_text, rec_codes, rec_labels, rec_reasons = "", (), (), ()
        try:
            result = await interactor.ask(case.prompt)
            answer_text = result.text
            area_map = market.area_map
            rec_codes = tuple(int(r.id) for r in result.recommendations)
            rec_labels = tuple(
                f"{area_map[c].trdar_name}|{area_map[c].district_name}"
                f"|{area_map[c].adm_dong_name}"
                for c in rec_codes if c in area_map
            )
            rec_reasons = tuple(r.reason for r in result.recommendations)
        except Exception as exc:  # 케이스 실패도 데이터 — 러너는 계속 간다
            error = f"{type(exc).__name__}: {exc}"

        # 실제 라우팅된 분기 — 스텁 호출 기록으로 확정한다
        if stocks.queries:
            final_intent = "stock"
        elif gemini.prompts:
            final_intent = "general"
        elif any(t is None and lim == 8 for _, t, lim in news.calls):
            final_intent = "market_news"
        elif market.summary_calls:
            final_intent = "market"
        else:
            final_intent = "unknown"

        traces.append(CaseTrace(
            case_id=case.case_id,
            final_intent=final_intent,
            stock_query=stocks.queries[0] if stocks.queries else "",
            answer_text=answer_text,
            calls=tuple(recorder.calls),
            phase1_raw_codes=_phase1_raw_codes(recorder.calls),
            recommendation_codes=rec_codes,
            recommendation_labels=rec_labels,
            recommendation_reasons=rec_reasons,
            seeded_history_codes=seeded,
            error=error,
        ))
        print(f"[eval] {case.case_id} intent={final_intent}"
              f" calls={len(recorder.calls)} error={error or '-'}")

    TRACE_PATH.write_text(
        "\n".join(json.dumps(t.to_dict(), ensure_ascii=False) for t in traces) + "\n",
        encoding="utf-8",
    )
    assert len(traces) == len(cases)
    print(f"[eval] trace 저장: {TRACE_PATH} ({len(traces)}건,"
          f" 실스냅샷={SnapshotMarket().is_real})")
