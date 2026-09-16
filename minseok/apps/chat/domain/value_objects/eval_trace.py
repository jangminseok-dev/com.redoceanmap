"""평가 골든셋 케이스와 실행 트레이스 — 값 객체.

러너(tests/eval/test_eval_runner.py)가 기록하고 채점기
(domain/services/eval_scorer.py)가 읽는 공용 자료구조.
표준 라이브러리만 사용한다(도메인 순수성 — app/adapter import 금지).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class EvalCase:
    """골든셋 한 문항 — tests/eval/golden_set.jsonl 한 줄."""

    case_id: str
    # market_region | market_noregion | market_nonseoul | market_finance
    # | stock_kr | stock_us | stock_fuzzy | market_news | general | multiturn
    category: str
    prompt: str
    expected_intent: str                       # stock | market_news | market | general
    accepted_queries: tuple[str, ...] = ()     # stock 계열 — 허용 종목 질의(정규화 후보 포함)
    region: str | None = None                  # market_region·nonseoul — 적중 판정 지명
    history_regions: tuple[str, ...] = ()      # multiturn — 직전 추천을 시딩할 지역

    @staticmethod
    def from_dict(d: dict) -> "EvalCase":
        return EvalCase(
            case_id=d["case_id"],
            category=d["category"],
            prompt=d["prompt"],
            expected_intent=d["expected_intent"],
            accepted_queries=tuple(d.get("accepted_queries") or ()),
            region=d.get("region"),
            history_regions=tuple(d.get("history_regions") or ()),
        )


@dataclass(frozen=True)
class LlmCall:
    """LLM 호출 1건 — 러너의 기록 프록시가 남긴다."""

    phase: str        # phase0 | phase1 | phase2 | stock_answer | market_news_answer | unknown
    prompt: str
    response: str
    latency_ms: float


@dataclass(frozen=True)
class CaseTrace:
    """케이스 1건의 실행 결과 — tests/eval/trace.jsonl 한 줄."""

    case_id: str
    final_intent: str                              # 실제 라우팅된 분기
    stock_query: str                               # 시스템이 추출한 종목 질의("" = 미추출)
    answer_text: str
    calls: tuple[LlmCall, ...] = ()
    phase1_raw_codes: tuple[int, ...] = ()         # phase1 LLM 원답(결정론 가드 보정 전)
    recommendation_codes: tuple[int, ...] = ()     # 최종 추천 상권(보정 후)
    recommendation_labels: tuple[str, ...] = ()    # "상권명|자치구|행정동"
    recommendation_reasons: tuple[str, ...] = ()
    seeded_history_codes: tuple[int, ...] = ()     # multiturn — 러너가 시딩한 직전 추천
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "CaseTrace":
        return CaseTrace(
            case_id=d["case_id"],
            final_intent=d["final_intent"],
            stock_query=d["stock_query"],
            answer_text=d["answer_text"],
            calls=tuple(LlmCall(**c) for c in d.get("calls") or ()),
            phase1_raw_codes=tuple(d.get("phase1_raw_codes") or ()),
            recommendation_codes=tuple(d.get("recommendation_codes") or ()),
            recommendation_labels=tuple(d.get("recommendation_labels") or ()),
            recommendation_reasons=tuple(d.get("recommendation_reasons") or ()),
            seeded_history_codes=tuple(d.get("seeded_history_codes") or ()),
            error=d.get("error"),
        )
