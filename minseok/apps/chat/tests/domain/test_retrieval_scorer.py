"""retrieval_scorer 테스트 — 지표 산식(손계산 대조)과 결정론을 고정한다."""
from __future__ import annotations

import math

from chat.domain.services.retrieval_scorer import (
    average_precision,
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
    score,
)
from chat.domain.value_objects.retrieval_trace import RetrievalCase, RetrievalTrace

# 라벨: 관련 3건(2·1·1등급) + 무관 1건. 결과 랭킹: [정답급, 무관, 관련, pool 밖, 관련]
LABELS = {"d1": 2, "d2": 1, "d3": 1, "d9": 0}
RESULTS = ("d1", "d9", "d2", "unlabeled", "d3")


def test_recall_at_k_손계산과_일치한다():
    # top-3 안의 관련 = d1, d2 → 2/3. top-5 = d1, d2, d3 → 3/3
    assert recall_at_k(RESULTS, LABELS, 3) == 2 / 3
    assert recall_at_k(RESULTS, LABELS, 5) == 1.0


def test_ndcg_at_k_지수_이득_손계산과_일치한다():
    # 이득: 등급 2→3, 1→1, 0·pool 밖→0
    # DCG@5 = 3/log2(2) + 0 + 1/log2(4) + 0 + 1/log2(6)
    dcg = 3 / math.log2(2) + 1 / math.log2(4) + 1 / math.log2(6)
    # 이상적 순서 [2,1,1] → IDCG = 3/log2(2) + 1/log2(3) + 1/log2(4)
    idcg = 3 / math.log2(2) + 1 / math.log2(3) + 1 / math.log2(4)
    assert ndcg_at_k(RESULTS, LABELS, 5) == dcg / idcg
    # 완벽한 랭킹이면 1.0
    assert ndcg_at_k(("d1", "d2", "d3"), LABELS, 5) == 1.0


def test_mrr과_map_손계산과_일치한다():
    assert reciprocal_rank(RESULTS, LABELS) == 1.0
    assert reciprocal_rank(("d9", "unlabeled", "d2"), LABELS) == 1 / 3
    assert reciprocal_rank(("d9", "unlabeled"), LABELS) == 0.0
    # AP = (1/1 + 2/3 + 3/5) / 3 — 관련 문서 위치 1·3·5의 precision 평균
    assert average_precision(RESULTS, LABELS) == (1 + 2 / 3 + 3 / 5) / 3


def test_score는_pending과_no_relevant를_평균에서_뺀다():
    cases = [
        RetrievalCase("A", "stock", "q1", labels=dict(LABELS)),
        RetrievalCase("B", "stock", "q2", labels={}),               # 라벨링 전
        RetrievalCase("C", "market", "q3", labels={"x": 0}),        # 관련 0개
        RetrievalCase("D", "market", "q4", labels={"m1": 1}),
        RetrievalCase("E", "market", "q5", labels={"m1": 1}),       # 트레이스 없음
    ]
    traces = [
        RetrievalTrace("A", results=RESULTS),
        RetrievalTrace("B", results=("d1",)),
        RetrievalTrace("C", results=("x",)),
        RetrievalTrace("D", results=("m9", "m1")),
        RetrievalTrace("F", results=(), error="검색 실패"),  # 골든셋에 없는 id — 무시
    ]
    report = score(cases, traces)
    assert report.total == 5
    assert report.pending == ("B",)
    assert report.no_relevant == ("C",)
    assert report.missing_trace == ("E",)
    assert report.overall is not None and report.overall.scored == 2
    assert set(report.by_category) == {"stock", "market"}
    assert report.by_category["market"].mrr == 0.5  # D: 첫 관련이 2위


def test_결정론_같은_입력이면_리포트가_동일하다():
    cases = [RetrievalCase("A", "stock", "q", labels=dict(LABELS))]
    traces = [RetrievalTrace("A", results=RESULTS)]
    assert score(cases, traces) == score(list(cases), list(traces))
