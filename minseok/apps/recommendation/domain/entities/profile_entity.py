from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# 투자·창업 프로파일 어휘 — 정확한 금액 대신 밴드(구간)만 받는다. 개인 금융 정보의
# 저장 부담을 낮추면서 개인화(서술 관점 조정)에는 충분한 해상도다. 라벨의 단일 정의처는
# 이 모듈이다 — 허브 계약으로 나가는 문장도 여기서 만든다(문장 소유자는 도메인).
PURPOSES: dict[str, str] = {
    "startup": "창업 준비",
    "invest": "주식 투자",
    "both": "창업·투자 둘 다",
}
# 증권사 투자성향 5등급 표준
RISK_LABELS: dict[int, str] = {
    1: "안정형",
    2: "안정추구형",
    3: "위험중립형",
    4: "적극투자형",
    5: "공격투자형",
}
BUDGET_BANDS: dict[str, str] = {
    "under_30m": "3천만원 미만",
    "30m_50m": "3천만~5천만원",
    "50m_100m": "5천만~1억원",
    "100m_300m": "1억~3억원",
    "over_300m": "3억원 이상",
}
DEBT_BURDENS: dict[str, str] = {
    "none": "부채 없음",
    "manageable": "부채 감당 가능",
    "heavy": "부채 부담됨",
}
HORIZONS: dict[str, str] = {
    "short": "단기(1년 미만)",
    "mid": "중기(1~3년)",
    "long": "장기(3년 이상)",
}


@dataclass(frozen=True)
class InvestorProfile:
    """사용자 투자·창업 프로파일 1건 — 자기신고 설문(사용자당 1행).

    북마크와 같은 "사용자 ↔ 분석 대상" 축의 심화라 이 스포크가 소유한다(ROADMAP 판정 —
    개인화는 recommendation 확장). 마이데이터 연동 없이 설문 밴드만 저장한다.
    """

    user_id: int
    purpose: str        # startup | invest | both
    risk_level: int     # 1(안정형) ~ 5(공격투자형)
    budget_band: str    # BUDGET_BANDS 키
    debt_burden: str    # none | manageable | heavy
    horizon: str        # short | mid | long
    updated_at: datetime | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if self.user_id <= 0:
            raise ValueError("InvestorProfile은 user_id가 필수입니다.")
        if self.purpose not in PURPOSES:
            raise ValueError(f"purpose는 {tuple(PURPOSES)} 중 하나여야 합니다: {self.purpose}")
        if self.risk_level not in RISK_LABELS:
            raise ValueError(f"risk_level은 1~5여야 합니다: {self.risk_level}")
        if self.budget_band not in BUDGET_BANDS:
            raise ValueError(f"budget_band는 {tuple(BUDGET_BANDS)} 중 하나여야 합니다: {self.budget_band}")
        if self.debt_burden not in DEBT_BURDENS:
            raise ValueError(f"debt_burden은 {tuple(DEBT_BURDENS)} 중 하나여야 합니다: {self.debt_burden}")
        if self.horizon not in HORIZONS:
            raise ValueError(f"horizon은 {tuple(HORIZONS)} 중 하나여야 합니다: {self.horizon}")

    @property
    def purpose_label(self) -> str:
        return PURPOSES[self.purpose]

    @property
    def risk_label(self) -> str:
        return RISK_LABELS[self.risk_level]

    @property
    def budget_label(self) -> str:
        return BUDGET_BANDS[self.budget_band]

    @property
    def debt_label(self) -> str:
        return DEBT_BURDENS[self.debt_burden]

    @property
    def horizon_label(self) -> str:
        return HORIZONS[self.horizon]
