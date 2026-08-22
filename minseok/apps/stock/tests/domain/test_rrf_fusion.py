"""rrf_fusion 테스트 — 결합 규칙 손계산 대조와 결정론을 고정한다."""
from __future__ import annotations

from stock.domain.services.rrf_fusion import rrf_merge


def test_양_채널_상위가_한_채널_1위보다_앞선다():
    # doc 7: 1/(60+2) + 1/(60+1) ≈ 0.0325 > doc 1: 1/(60+1) ≈ 0.0164 > doc 9: 1/(60+2)
    merged = rrf_merge([[1, 7], [7, 9]])
    assert merged == [7, 1, 9]


def test_한_채널이_비어도_다른_채널_순서가_유지된다():
    assert rrf_merge([[3, 1, 2], []]) == [3, 1, 2]
    assert rrf_merge([[], []]) == []


def test_동점은_문서_키_오름차순으로_결정론이다():
    # 두 문서가 서로 다른 채널의 같은 순위 — 점수 동률
    assert rrf_merge([[5], [2]]) == [2, 5]
    assert rrf_merge([[5], [2]]) == rrf_merge([[5], [2]])
