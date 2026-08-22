"""R3 청킹 비교 리포트 — (a) 고정 토큰 vs (b) 섹션 vs (c) 표 인지를 같은 라벨로 채점.

게이트 판정 재료를 출력한다: **(c)가 (a) 대비 표 질의(disclosure_table)의 recall@5
+0.10 이상**이면 표 인지 청킹 채택, 미달이면 청킹 고도화를 기각하고 (a) 고정 토큰
유지 — 기각도 동등하게 유효한 결과다(ROADMAP R3, E2 선례). 채택을 강제하지 않는다
(assert 없음). 검증하는 것은 같은 라벨 표본으로 채점됐다는 비교 성립 조건뿐이다.

트레이스 3벌이 없으면 skip — 러너(minseok/tests/test_retrieval_disclosure_runner.py,
-m ollama) 먼저. 라벨이 없으면 skip — pooling 시트에 사람이 0/1/2를 붙인 뒤 실행.
"""
from __future__ import annotations

import pytest

from chat.domain.services.retrieval_scorer import score
from chat.tests.eval.retrieval import (
    DISCLOSURE_STRATEGIES,
    RETRIEVAL_GOLDEN_DISCLOSURE_PATH,
    RETRIEVAL_TRACE_DISCLOSURE_PATHS,
    load_retrieval_cases,
    load_retrieval_traces,
)

R3_TABLE_RECALL5_MARGIN = 0.10  # 채택 게이트 — ROADMAP R3
STRATEGY_LABELS = {"a": "고정 토큰(대조군)", "b": "섹션 분할", "c": "표 인지"}


def test_retrieval_chunking_report():
    missing = [s for s in DISCLOSURE_STRATEGIES
               if not RETRIEVAL_TRACE_DISCLOSURE_PATHS[s].exists()]
    if missing:
        pytest.skip(f"트레이스 없음({missing}) — 공시 러너(-m ollama)를 먼저 실행")

    cases = load_retrieval_cases(RETRIEVAL_GOLDEN_DISCLOSURE_PATH)
    reports = {
        s: score(cases, load_retrieval_traces(RETRIEVAL_TRACE_DISCLOSURE_PATHS[s]))
        for s in DISCLOSURE_STRATEGIES
    }
    if any(r.overall is None for r in reports.values()):
        pytest.skip("라벨된 케이스 0건 — pooling 시트에 사람 라벨을 붙인 뒤 실행")

    scored = {s: r.overall.scored for s, r in reports.items()}
    assert len(set(scored.values())) == 1, f"채점 표본 불일치: {scored}"

    print(f"\n[chunking-report] 채점 {reports['a'].overall.scored}건")
    for s, r in reports.items():
        print(f"[chunking-report] ({s}) {STRATEGY_LABELS[s]}: {r.overall.to_dict()}")
        table = r.by_category.get("disclosure_table")
        if table:
            print(f"[chunking-report]   표 질의 recall@5={table.recall_at_5:.3f}"
                  f" nDCG@5={table.ndcg_at_5:.3f} ({table.scored}건)")

    table_a = reports["a"].by_category.get("disclosure_table")
    table_c = reports["c"].by_category.get("disclosure_table")
    if table_a is None or table_c is None:
        pytest.skip("표 질의(disclosure_table) 라벨 없음 — 게이트 판정 불가")
    delta = table_c.recall_at_5 - table_a.recall_at_5
    verdict = "채택 게이트 통과 — 표 인지 청킹 채택" if delta >= R3_TABLE_RECALL5_MARGIN \
        else "게이트 미달 — 청킹 고도화 기각, (a) 고정 토큰 유지"
    print(f"[chunking-report] 표 질의 recall@5 델타 (c)-(a) = {delta:+.3f}"
          f" (기준 +{R3_TABLE_RECALL5_MARGIN}) → {verdict}")
