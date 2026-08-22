"""검색 평가(R1) 골든셋 케이스와 실행 트레이스 — 값 객체.

러너(minseok/tests/test_retrieval_runner.py)가 기록하고 채점기
(domain/services/retrieval_scorer.py)가 읽는 공용 자료구조.
표준 라이브러리만 사용한다(도메인 순수성 — app/adapter import 금지).

문서 키는 코퍼스 행 id의 문자열이다(stock=news_articles.id · market=market_news_articles.id).
케이스 하나는 한 코퍼스만 검색하므로 두 테이블의 id가 겹쳐도 모호하지 않다.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class RetrievalCase:
    """골든셋 한 문항 — tests/eval/retrieval_golden.jsonl 한 줄.

    labels는 TREC pooling 방식 사람 라벨(문서 키 → 0/1/2 등급)이다.
    ⛔ 라벨링을 LLM에 시키지 않는다 — 단일 모델 정책상 7.8B가 자기 검색을 심판하는
    순환이 된다(eval_scorer가 LLM-as-judge를 배제한 것과 같은 이유).
    비어 있으면 라벨링 전(pending) — 채점에서 제외된다.
    """

    case_id: str
    category: str                            # stock | market — 어느 코퍼스를 검색하는가
    query: str
    labels: dict[str, int] = field(default_factory=dict)  # 문서 키 → 0(무관)/1(관련)/2(정답급)

    @staticmethod
    def from_dict(d: dict) -> "RetrievalCase":
        return RetrievalCase(
            case_id=d["case_id"],
            category=d["category"],
            query=d["query"],
            labels={str(k): int(v) for k, v in (d.get("labels") or {}).items()},
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalTrace:
    """케이스 1건의 검색 결과 — tests/eval/retrieval_trace.jsonl 한 줄.

    results는 랭킹 순 문서 키(상위가 앞). 라벨에 없는 문서는 채점 시 0등급으로
    간주한다(pooling 가정 — pool 밖 문서를 관련으로 쳐줄 근거가 없다).
    """

    case_id: str
    results: tuple[str, ...] = ()
    error: str | None = None

    @staticmethod
    def from_dict(d: dict) -> "RetrievalTrace":
        return RetrievalTrace(
            case_id=d["case_id"],
            results=tuple(str(r) for r in (d.get("results") or ())),
            error=d.get("error"),
        )

    def to_dict(self) -> dict:
        return asdict(self)
