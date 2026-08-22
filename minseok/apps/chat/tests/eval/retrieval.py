"""검색 평가(R1) 골든셋·트레이스 로더 — 러너(minseok/tests)와 게이트가 공유한다."""
from __future__ import annotations

import json
from pathlib import Path

from chat.domain.value_objects.retrieval_trace import RetrievalCase, RetrievalTrace

EVAL_DIR = Path(__file__).parent
RETRIEVAL_GOLDEN_PATH = EVAL_DIR / "retrieval_golden.jsonl"
RETRIEVAL_TRACE_PATH = EVAL_DIR / "retrieval_trace.jsonl"
# R2 하이브리드(벡터+trigram RRF) 트레이스 — 같은 골든셋·라벨로 현행과 비교 채점한다
RETRIEVAL_TRACE_HYBRID_PATH = EVAL_DIR / "retrieval_trace_hybrid.jsonl"
RETRIEVAL_POOL_PATH = EVAL_DIR / "retrieval_pool.jsonl"      # 사람 라벨링용 후보 시트(두 시스템 합집합)
RETRIEVAL_BASELINE_PATH = EVAL_DIR / "retrieval_baseline.json"


def load_retrieval_cases() -> list[RetrievalCase]:
    return [
        RetrievalCase.from_dict(json.loads(line))
        for line in RETRIEVAL_GOLDEN_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_retrieval_traces(path: Path = RETRIEVAL_TRACE_PATH) -> list[RetrievalTrace]:
    return [
        RetrievalTrace.from_dict(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
