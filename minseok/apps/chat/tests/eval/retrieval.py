"""검색 평가(R1) 골든셋·트레이스 로더 — 러너(minseok/tests)와 게이트가 공유한다."""
from __future__ import annotations

import json
from pathlib import Path

from chat.domain.value_objects.retrieval_trace import RetrievalCase, RetrievalTrace

EVAL_DIR = Path(__file__).parent
RETRIEVAL_GOLDEN_PATH = EVAL_DIR / "retrieval_golden.jsonl"
RETRIEVAL_TRACE_PATH = EVAL_DIR / "retrieval_trace.jsonl"
RETRIEVAL_POOL_PATH = EVAL_DIR / "retrieval_pool.jsonl"      # 사람 라벨링용 후보 시트
RETRIEVAL_BASELINE_PATH = EVAL_DIR / "retrieval_baseline.json"


def load_retrieval_cases() -> list[RetrievalCase]:
    return [
        RetrievalCase.from_dict(json.loads(line))
        for line in RETRIEVAL_GOLDEN_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_retrieval_traces() -> list[RetrievalTrace]:
    return [
        RetrievalTrace.from_dict(json.loads(line))
        for line in RETRIEVAL_TRACE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
