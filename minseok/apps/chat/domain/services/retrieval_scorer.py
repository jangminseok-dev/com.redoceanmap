"""검색 품질 채점기(R1) — recall@k · nDCG@k · MRR · mAP.

표준 라이브러리만 쓰는 순수 함수다(도메인 순수성). 같은 (골든셋, 트레이스) 입력이면
언제 몇 번을 돌려도 같은 결과가 나온다 — 결정론이 게이트의 전제다.

채점 규칙:
- 관련(binary) 판정: 등급 >= 1. 이득(graded): 2^등급 - 1 (TREC 표준 지수 이득 — 0/1/2 → 0/1/3).
- 라벨에 없는 문서는 0등급으로 간주한다(pooling 가정).
- recall 분모와 IDCG는 **라벨된 관련 문서 전체**다 — pool(코사인 top-20) 기반이므로
  pool 밖에 있을 관련 문서는 계량에 안 잡힌다. 이 한계는 절대 성능이 아니라
  **같은 골든셋 위의 상대 비교**(baseline 대비 회귀·개선)로 쓰는 이유다.
- 라벨이 비어 있는 케이스(pending)와 관련 문서가 0개인 케이스(no_relevant)는
  평균에서 제외하고 건수로 보고한다 — 0으로 섞으면 라벨 진행률이 점수를 흔든다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from chat.domain.value_objects.retrieval_trace import RetrievalCase, RetrievalTrace

RECALL_KS = (5, 10)
NDCG_KS = (5, 10)


def _gain(grade: int) -> float:
    return float(2 ** grade - 1)


def recall_at_k(results: tuple[str, ...], labels: dict[str, int], k: int) -> float:
    """상위 k에 든 관련 문서 수 / 라벨된 관련 문서 총수. 관련 0개면 호출부가 걸러야 한다."""
    relevant = {doc for doc, grade in labels.items() if grade >= 1}
    hit = sum(1 for doc in results[:k] if doc in relevant)
    return hit / len(relevant)


def ndcg_at_k(results: tuple[str, ...], labels: dict[str, int], k: int) -> float:
    """지수 이득 DCG@k / 이상적 순서의 IDCG@k. 관련 0개면 호출부가 걸러야 한다."""
    dcg = sum(
        _gain(labels.get(doc, 0)) / math.log2(rank + 1)
        for rank, doc in enumerate(results[:k], start=1)
    )
    ideal = sorted((g for g in labels.values() if g >= 1), reverse=True)[:k]
    idcg = sum(_gain(g) / math.log2(rank + 1) for rank, g in enumerate(ideal, start=1))
    return dcg / idcg if idcg > 0 else 0.0


def reciprocal_rank(results: tuple[str, ...], labels: dict[str, int]) -> float:
    """첫 관련 문서의 1/순위 — 결과 안에 관련이 하나도 없으면 0."""
    for rank, doc in enumerate(results, start=1):
        if labels.get(doc, 0) >= 1:
            return 1.0 / rank
    return 0.0


def average_precision(results: tuple[str, ...], labels: dict[str, int]) -> float:
    """AP — Σ(관련 문서 위치의 precision) / 라벨된 관련 문서 총수(이진 관련)."""
    relevant = {doc for doc, grade in labels.items() if grade >= 1}
    hit = 0
    precision_sum = 0.0
    for rank, doc in enumerate(results, start=1):
        if doc in relevant:
            hit += 1
            precision_sum += hit / rank
    return precision_sum / len(relevant)


@dataclass(frozen=True)
class CategoryMetrics:
    """한 카테고리(또는 전체)의 평균 지표 — 채점된 케이스 수 동반."""

    scored: int
    recall_at_5: float
    recall_at_10: float
    ndcg_at_5: float
    ndcg_at_10: float
    mrr: float
    map: float

    def to_dict(self) -> dict:
        return {
            "scored": self.scored,
            "recall_at_5": self.recall_at_5,
            "recall_at_10": self.recall_at_10,
            "ndcg_at_5": self.ndcg_at_5,
            "ndcg_at_10": self.ndcg_at_10,
            "mrr": self.mrr,
            "map": self.map,
        }


@dataclass(frozen=True)
class RetrievalReport:
    total: int
    pending: tuple[str, ...] = ()       # 라벨 없는 케이스(라벨링 전)
    no_relevant: tuple[str, ...] = ()   # 라벨은 있으나 관련 문서 0개 — 라벨 재검토 신호
    missing_trace: tuple[str, ...] = ()
    errored: tuple[str, ...] = ()
    overall: CategoryMetrics | None = None
    by_category: dict[str, CategoryMetrics] = field(default_factory=dict)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _aggregate(rows: list[dict[str, float]]) -> CategoryMetrics:
    return CategoryMetrics(
        scored=len(rows),
        recall_at_5=_mean([r["recall_at_5"] for r in rows]),
        recall_at_10=_mean([r["recall_at_10"] for r in rows]),
        ndcg_at_5=_mean([r["ndcg_at_5"] for r in rows]),
        ndcg_at_10=_mean([r["ndcg_at_10"] for r in rows]),
        mrr=_mean([r["mrr"] for r in rows]),
        map=_mean([r["map"] for r in rows]),
    )


def score(cases: list[RetrievalCase], traces: list[RetrievalTrace]) -> RetrievalReport:
    """골든셋 × 트레이스 → 리포트. 순수 함수 — 같은 입력이면 항상 같은 출력."""
    trace_by_id = {t.case_id: t for t in traces}
    pending: list[str] = []
    no_relevant: list[str] = []
    missing_trace: list[str] = []
    errored: list[str] = []
    per_case: list[tuple[str, dict[str, float]]] = []

    for case in cases:
        trace = trace_by_id.get(case.case_id)
        if trace is None:
            missing_trace.append(case.case_id)
            continue
        if trace.error:
            errored.append(case.case_id)
            continue
        if not case.labels:
            pending.append(case.case_id)
            continue
        if not any(grade >= 1 for grade in case.labels.values()):
            no_relevant.append(case.case_id)
            continue
        per_case.append((case.category, {
            "recall_at_5": recall_at_k(trace.results, case.labels, 5),
            "recall_at_10": recall_at_k(trace.results, case.labels, 10),
            "ndcg_at_5": ndcg_at_k(trace.results, case.labels, 5),
            "ndcg_at_10": ndcg_at_k(trace.results, case.labels, 10),
            "mrr": reciprocal_rank(trace.results, case.labels),
            "map": average_precision(trace.results, case.labels),
        }))

    by_category = {
        category: _aggregate([row for cat, row in per_case if cat == category])
        for category in sorted({cat for cat, _ in per_case})
    }
    return RetrievalReport(
        total=len(cases),
        pending=tuple(pending),
        no_relevant=tuple(no_relevant),
        missing_trace=tuple(missing_trace),
        errored=tuple(errored),
        overall=_aggregate([row for _, row in per_case]) if per_case else None,
        by_category=by_category,
    )
