"""골든셋·트레이스 파일 로더 — 러너와 게이트가 공유한다."""
from __future__ import annotations

import json
from pathlib import Path

from chat.domain.value_objects.eval_trace import CaseTrace, EvalCase

EVAL_DIR = Path(__file__).parent
GOLDEN_PATH = EVAL_DIR / "golden_set.jsonl"
TRACE_PATH = EVAL_DIR / "trace.jsonl"
BASELINE_PATH = EVAL_DIR / "baseline.json"


def load_cases() -> list[EvalCase]:
    return [
        EvalCase.from_dict(json.loads(line))
        for line in GOLDEN_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_traces() -> list[CaseTrace]:
    return [
        CaseTrace.from_dict(json.loads(line))
        for line in TRACE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
