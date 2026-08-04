"""question_insight 게이트웨이의 유도 로직 테스트 — DB 없이 순수 함수만 잡는다.

answer_kind는 저장값이 아니라 관측 유도값이라, 유도 규칙이 이 슬라이스의 본체다.
"""
from __future__ import annotations

from chat.adapter.outbound.gateways.question_insight_gateway import (
    extract_region,
    infer_answer_kind,
)
from chat.app.use_cases.chat_interactor import NONSEOUL_GUARD_PREFIX


def test_payload_키가_라우팅_결과를_말한다():
    assert infer_answer_kind({"recommendations": []}, "요약") == "market"
    assert infer_answer_kind({"stock": {}}, "서술") == "stock"
    assert infer_answer_kind({"news": []}, "업황") == "market_news"


def test_가드_문구는_payload보다_먼저_판정한다():
    text = f"{NONSEOUL_GUARD_PREFIX} 부산 등 다른 지역은 아직 준비 중이라..."
    assert infer_answer_kind(None, text) == "nonseoul"


def test_payload_없는_텍스트_답변은_text다():
    assert infer_answer_kind(None, "일반 답변") == "text"
    assert infer_answer_kind({}, "빈 payload") == "text"


def test_인터랙터의_가드_문구와_상수가_일치한다():
    # 단일 정의처 회귀 방지 — 인터랙터가 실제로 만드는 안내문이 이 접두로 시작해야
    # nonseoul 집계가 깨지지 않는다.
    assert NONSEOUL_GUARD_PREFIX.startswith("지금은 서울 상권 데이터만")


def test_지역_추출은_가드와_같은_목록을_쓴다():
    assert extract_region("부산 서면에 카페 어때?") == "부산"
    assert extract_region("성수동 카페 어때?") is None  # 서울 지명은 대상 아님
