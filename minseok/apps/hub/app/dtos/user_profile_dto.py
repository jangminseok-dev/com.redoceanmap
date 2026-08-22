from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UserProfileSummary:
    """사용자 투자·창업 프로파일 요약 — 소비자(chat)가 프롬프트에 그대로 싣는 문장 라벨.

    라벨 문장의 소유자는 구현 스포크(recommendation) 도메인이다 — 원시 코드로 내리면
    라벨 매핑이 소비자마다 중복 구현된다(AreaScoreInfo.grade 선례). purpose만 원시값을
    함께 나른다(소비자가 상권/주식 어느 축에 주입할지 분기하는 키).
    """

    purpose: str          # startup | invest | both
    purpose_label: str    # 예: "창업 준비"
    risk_label: str       # 예: "안정추구형"
    budget_label: str     # 예: "5천만~1억원"
    debt_label: str       # 예: "부채 없음"
    horizon_label: str    # 예: "중기(1~3년)"
