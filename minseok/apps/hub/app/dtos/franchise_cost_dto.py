"""공정위 가맹정보 업종별 창업비용 — 상권 축의 "이 예산이면 어떤 업종이 되나"를 채우는 계약 DTO.

금액은 전부 원(KRW). 원천은 정보공개서 평균이라 **가맹 기준**(가맹금·교육비·보증금·기타)이고
점포 임대료·인테리어는 들어 있지 않다 — 소비자는 그 한계를 함께 말해야 한다.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class FranchiseCostItem:
    year: int
    sector: str          # 외식 | 도소매 | 서비스
    industry_name: str   # 업종중분류명(예: 커피, 치킨)
    franchise_fee: int
    education_fee: int
    deposit: int
    other_fee: int
    total_amount: int
    brand_count: int | None = None
    raw: dict | None = None


@dataclass(frozen=True)
class StartupCostRow:
    """읽기용 — 채팅이 예산 질문에 쓴다."""

    year: int
    sector: str
    industry_name: str
    total_amount: int
    franchise_fee: int
    education_fee: int
    deposit: int
    other_fee: int
