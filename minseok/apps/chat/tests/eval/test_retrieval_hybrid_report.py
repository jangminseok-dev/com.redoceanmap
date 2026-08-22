"""R2 하이브리드 비교 리포트 — 현행(코사인) vs 하이브리드(벡터+trigram RRF)를 같은 라벨로 채점.

게이트 판정 재료를 출력한다: **nDCG@5가 현행 대비 +0.03 이상**이면 채택(포트·유스케이스
전환은 별도 커밋), 미달이면 기각하고 현행 유지 — 기각도 동등하게 유효한 결과다(E2 선례).
이 테스트는 채택을 강제하지 않는다(assert 없음 — 미달이 테스트 실패가 아니다). 검증하는
것은 두 트레이스가 같은 라벨 표본으로 채점됐다는 비교 성립 조건뿐이다.

trace 2벌이 없으면 skip — 러너(minseok/tests/test_retrieval_runner.py, -m ollama) 먼저.
라벨이 없으면 skip — retrieval_pool.jsonl(두 시스템 합집합)에 사람이 0/1/2를 붙인 뒤 실행.
"""
from __future__ import annotations

import pytest

from chat.domain.services.retrieval_scorer import score
from chat.tests.eval.retrieval import (
    RETRIEVAL_TRACE_HYBRID_PATH,
    RETRIEVAL_TRACE_PATH,
    load_retrieval_cases,
    load_retrieval_traces,
)

R2_NDCG5_MARGIN = 0.03  # 채택 게이트 — ROADMAP R2


def test_retrieval_hybrid_report():
    if not (RETRIEVAL_TRACE_PATH.exists() and RETRIEVAL_TRACE_HYBRID_PATH.exists()):
        pytest.skip("트레이스 2벌 없음 — 러너(-m ollama)를 먼저 실행")

    cases = load_retrieval_cases()
    base = score(cases, load_retrieval_traces(RETRIEVAL_TRACE_PATH))
    hybrid = score(cases, load_retrieval_traces(RETRIEVAL_TRACE_HYBRID_PATH))
    if base.overall is None or hybrid.overall is None:
        pytest.skip("라벨된 케이스 0건 — pooling 시트에 사람 라벨을 붙인 뒤 실행")

    # 비교 성립 조건 — 같은 라벨 표본으로 채점됐어야 델타가 의미를 가진다
    assert base.overall.scored == hybrid.overall.scored, (
        f"채점 표본 불일치: 현행 {base.overall.scored} vs 하이브리드 {hybrid.overall.scored}"
    )

    print(f"\n[hybrid-report] 채점 {base.overall.scored}건")
    print(f"[hybrid-report] 현행     {base.overall.to_dict()}")
    print(f"[hybrid-report] 하이브리드 {hybrid.overall.to_dict()}")
    for category in sorted(set(base.by_category) & set(hybrid.by_category)):
        print(f"[hybrid-report] {category}: nDCG@5"
              f" {base.by_category[category].ndcg_at_5:.3f}"
              f" → {hybrid.by_category[category].ndcg_at_5:.3f}")

    delta = hybrid.overall.ndcg_at_5 - base.overall.ndcg_at_5
    verdict = "채택 게이트 통과 — 포트·유스케이스 전환 진행" if delta >= R2_NDCG5_MARGIN \
        else "게이트 미달 — 기각하고 현행 순수 코사인 유지"
    print(f"[hybrid-report] nDCG@5 델타 {delta:+.3f} (기준 +{R2_NDCG5_MARGIN}) → {verdict}")
