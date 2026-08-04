"""품질 게이트 — trace.jsonl을 채점해 절대 규칙·회귀를 검증한다. LLM 불필요.

- 절대 규칙(타협 없음): 금지 표현 0건 · 책임 고지 100% · 입지 창작 0건 ·
  서울 외 지역 결정론 가드 100%
- 회귀 규칙: baseline.json 대비 -3%p 이상 하락 시 실패, 환각 숫자 건수 증가 시 실패.
  baseline이 없으면 현재 실측을 baseline으로 기록한다(첫 실행 부트스트랩).
- trace.jsonl이 없으면 skip — 러너(test_eval_runner.py, -m ollama)를 먼저 돌린다.
"""
from __future__ import annotations

import json

import pytest

from chat.domain.services.eval_scorer import score
from chat.tests.eval.golden import BASELINE_PATH, TRACE_PATH, load_cases, load_traces

_REGRESSION_KEYS = (
    "intent_accuracy", "stock_query_accuracy", "region_hit_rate", "inherit_success_rate",
)
_REGRESSION_TOLERANCE = 0.03  # -3%p


def test_quality_gate():
    if not TRACE_PATH.exists():
        pytest.skip("trace.jsonl 없음 — 러너(test_eval_runner.py, -m ollama) 먼저 실행")

    report = score(load_cases(), load_traces())
    hallucinations = [v for v in report.violations if v.rule == "hallucinated_number"]
    absolute = [v for v in report.violations if v.rule != "hallucinated_number"]

    print(f"\n[gate] 케이스 {report.total}건 (오류 {len(report.errored)}건: {report.errored})")
    print(f"[gate] intent_accuracy={report.intent_accuracy:.3f}"
          f" confusion={report.intent_confusion}")
    print(f"[gate] stock_query_accuracy={report.stock_query_accuracy}"
          f" phase0_parse_failure={report.phase0_parse_failure_rate:.3f}")
    print(f"[gate] region_hit={report.region_hit_rate}"
          f" guard_activation={report.phase1_guard_activation_rate}"
          f" inherit={report.inherit_success_rate}"
          f" nonseoul_guard={report.nonseoul_guard_rate}")
    print(f"[gate] latency p50={report.latency_p50_ms} p95={report.latency_p95_ms}")
    print(f"[gate] 환각 의심 숫자 {len(hallucinations)}건, 절대 규칙 위반 {len(absolute)}건")

    # --- 절대 규칙 ---
    assert absolute == [], f"절대 규칙 위반: {absolute}"
    if report.nonseoul_guard_rate is not None:
        assert report.nonseoul_guard_rate == 1.0, (
            f"서울 외 지역 가드 실패율 발생: {report.nonseoul_guard_rate:.3f}"
        )

    # --- 회귀 규칙 ---
    current = {
        "intent_accuracy": report.intent_accuracy,
        "stock_query_accuracy": report.stock_query_accuracy,
        "region_hit_rate": report.region_hit_rate,
        "inherit_success_rate": report.inherit_success_rate,
        "phase0_parse_failure_rate": report.phase0_parse_failure_rate,
        "phase1_guard_activation_rate": report.phase1_guard_activation_rate,
        "hallucination_count": len(hallucinations),
        "total": report.total,
    }
    if not BASELINE_PATH.exists():
        BASELINE_PATH.write_text(
            json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        print(f"[gate] baseline 최초 기록: {BASELINE_PATH}")
        return

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    for key in _REGRESSION_KEYS:
        cur, base = current.get(key), baseline.get(key)
        if cur is None or base is None:
            continue
        assert cur >= base - _REGRESSION_TOLERANCE, (
            f"회귀: {key} {base:.3f} → {cur:.3f} (허용 -{_REGRESSION_TOLERANCE:.0%})"
        )
    assert current["hallucination_count"] <= baseline.get("hallucination_count", 0), (
        f"회귀: 환각 의심 숫자 {baseline.get('hallucination_count')}건"
        f" → {current['hallucination_count']}건 ({[v.detail for v in hallucinations]})"
    )
