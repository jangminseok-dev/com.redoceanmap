"""RRF(Reciprocal Rank Fusion) — 하이브리드 검색(R2)의 채널 결합 규칙.

score(doc) = Σ_channels 1/(k + rank), rank는 1부터. 점수 스케일이 다른 채널
(코사인 거리 vs trigram similarity)을 정규화 없이 순위만으로 섞는 표준 기법이다.
순수 함수 — 같은 입력이면 항상 같은 순서(동점은 문서 키 오름차순으로 결정론 고정).

market 앱에도 같은 소형 복제가 있다(스포크 상호 독립 — eval_scorer._parse_json 선례).
"""
from __future__ import annotations

from collections.abc import Sequence

RRF_K = 60  # 표준 상수 — 파라미터 스윕(R2 ③)의 대상


def rrf_merge(rankings: Sequence[Sequence[int]], k: int = RRF_K) -> list[int]:
    """채널별 문서 키 랭킹(상위가 앞)을 RRF 점수 내림차순 단일 랭킹으로 합친다."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, doc in enumerate(ranking, start=1):
            scores[doc] = scores.get(doc, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=lambda doc: (-scores[doc], doc))
