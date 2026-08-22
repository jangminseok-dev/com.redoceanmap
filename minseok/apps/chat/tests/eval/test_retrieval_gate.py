"""검색 품질 게이트(R1) — retrieval_trace.jsonl을 채점해 결정론·회귀를 검증한다. LLM 불필요.

- 절대 규칙: 같은 트레이스 재채점 시 동일 결과(결정론) · 검색 오류 케이스 0건.
- 회귀 규칙: retrieval_baseline.json 대비 -0.03 이상 하락 시 실패(nDCG@5·recall@5/10·MRR·mAP).
  baseline이 없으면 현재 실측을 baseline으로 기록한다(첫 실행 부트스트랩) —
  R2(하이브리드)의 게이트 "nDCG@5 +0.03 이상"이 이 baseline을 기준으로 잰다.
- trace가 없으면 skip — 러너(minseok/tests/test_retrieval_runner.py, -m ollama·실 DB) 먼저.
- 라벨이 하나도 없으면 skip — pooling 후보(retrieval_pool.jsonl)에 사람이 0/1/2 등급을
  붙여 retrieval_golden.jsonl의 labels를 채워야 채점이 성립한다(LLM 라벨링 금지).
"""
from __future__ import annotations

import json

import pytest

from chat.domain.services.retrieval_scorer import score
from chat.tests.eval.retrieval import (
    RETRIEVAL_BASELINE_PATH,
    RETRIEVAL_TRACE_PATH,
    load_retrieval_cases,
    load_retrieval_traces,
)

_REGRESSION_KEYS = ("ndcg_at_5", "recall_at_5", "recall_at_10", "mrr", "map")
_REGRESSION_TOLERANCE = 0.03


def test_retrieval_gate():
    if not RETRIEVAL_TRACE_PATH.exists():
        pytest.skip("retrieval_trace.jsonl 없음 — 러너(minseok/tests/test_retrieval_runner.py, -m ollama) 먼저 실행")

    cases, traces = load_retrieval_cases(), load_retrieval_traces()
    report = score(cases, traces)

    # --- 절대 규칙: 결정론 — 같은 입력 재채점이 완전히 같은 리포트여야 한다 ---
    assert report == score(load_retrieval_cases(), load_retrieval_traces()), "채점 비결정론"
    # --- 절대 규칙: 검색 자체가 죽은 케이스는 게이트 이전 문제다 ---
    assert report.errored == (), f"검색 오류 케이스: {report.errored}"

    if report.overall is None:
        pytest.skip(
            f"라벨된 케이스 0건(pending {len(report.pending)}) — retrieval_pool.jsonl을 보고 "
            "사람이 retrieval_golden.jsonl의 labels를 채운 뒤 다시 실행"
        )

    print(f"\n[retrieval-gate] 케이스 {report.total}건: 채점 {report.overall.scored}"
          f" · pending {len(report.pending)} · no_relevant {report.no_relevant or '없음'}"
          f" · trace 누락 {report.missing_trace or '없음'}")
    print(f"[retrieval-gate] overall {report.overall.to_dict()}")
    for category, metrics in report.by_category.items():
        print(f"[retrieval-gate] {category} {metrics.to_dict()}")

    current = {
        **report.overall.to_dict(),
        "by_category": {c: m.to_dict() for c, m in report.by_category.items()},
        "pending": len(report.pending),
    }
    if not RETRIEVAL_BASELINE_PATH.exists():
        RETRIEVAL_BASELINE_PATH.write_text(
            json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        print(f"[retrieval-gate] baseline 최초 기록: {RETRIEVAL_BASELINE_PATH}")
        return

    baseline = json.loads(RETRIEVAL_BASELINE_PATH.read_text(encoding="utf-8"))
    # 라벨이 늘면(=채점 표본이 다르면) 점수는 비교 대상이 아니다 — baseline을 지우고 다시 잡는다.
    assert current["scored"] >= baseline.get("scored", 0), (
        f"채점 표본 감소: {baseline.get('scored')} → {current['scored']}"
        " (라벨을 지웠다면 baseline도 다시 잡을 것)"
    )
    for key in _REGRESSION_KEYS:
        cur, base = current.get(key), baseline.get(key)
        if cur is None or base is None:
            continue
        assert cur >= base - _REGRESSION_TOLERANCE, (
            f"회귀: {key} {base:.3f} → {cur:.3f} (허용 -{_REGRESSION_TOLERANCE})"
        )
