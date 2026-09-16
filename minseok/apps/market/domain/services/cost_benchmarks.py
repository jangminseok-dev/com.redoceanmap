"""업종군별 원가율·영업이익률 벤치마크 — 결정론 상수(KOSIS API 적재 안 함, FINANCE_ENGINE D3).

값은 소상공인실태조사 발표 표와 대조해 교체한다 — 대조 전까지 잠정치이며 source에 "잠정"을 남긴다.
B8 `PAYBACK_MARGIN`과 같은 방식: 가정치를 답변에 출처와 함께 병기한다.
"""
from __future__ import annotations

from dataclasses import dataclass

MIN_WAGE_HOURLY_2026 = 10_320   # 2026년 최저임금 시급(2025-07 고시)
MONTHLY_HOURS = 209             # 주 40시간 + 주휴 환산 월 근로시간
DEFAULT_SHOP_SQM = 33.0         # 면적 미입력 시 10평 가정
DEPOSIT_MONTHS = 10             # 보증금 미입력 시 월세 10개월분 가정
WORKING_CAPITAL_MONTHS = 3      # 개업 후 버틸 운전자금(고정비 N개월분)
DEFAULT_LOAN_RATE = 4.5         # ECOS 미적재 시 연 %

_SOURCE = "소상공인실태조사 2024(중기부·통계청) 대조 전 잠정치"


@dataclass(frozen=True)
class CostBenchmark:
    group: str
    label: str
    cost_ratio: float     # 매출 대비 재료비(변동비) 비율
    margin_ratio: float   # 영업이익률
    source: str


COST_BENCHMARKS: dict[str, CostBenchmark] = {
    "food": CostBenchmark("food", "음식점", 0.38, 0.12, _SOURCE),
    "cafe": CostBenchmark("cafe", "카페·음료", 0.30, 0.14, _SOURCE),
    "pub": CostBenchmark("pub", "주점", 0.35, 0.13, _SOURCE),
    "retail": CostBenchmark("retail", "소매", 0.72, 0.05, _SOURCE),
    "service": CostBenchmark("service", "미용·서비스", 0.15, 0.20, _SOURCE),
    "education": CostBenchmark("education", "교육", 0.05, 0.22, _SOURCE),
    "other": CostBenchmark("other", "기타", 0.30, 0.12, _SOURCE),
}

# 서울시 업종명 어간 → 업종군. 앞에서부터 처음 걸리는 것.
_GROUP_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("cafe", ("커피", "음료", "카페")),
    ("pub", ("주점", "호프", "맥주")),
    ("food", ("음식점", "분식", "치킨", "패스트푸드", "제과", "반찬", "피자", "족발", "요리")),
    ("retail", ("편의점", "슈퍼", "마트", "의류", "화장품", "서적", "문구", "가구", "전자", "안경",
                "철물", "조명", "시계", "가방", "신발", "핸드폰", "중고", "꽃", "애완", "완구", "청과", "정육", "수산")),
    ("service", ("미용", "네일", "피부", "세탁", "목욕", "노래", "당구", "PC", "볼링", "골프", "헬스", "스포츠", "사진", "인테리어", "자동차")),
    ("education", ("학원", "교습")),
)


def benchmark_for(service_name: str) -> CostBenchmark:
    for group, words in _GROUP_KEYWORDS:
        if any(w in service_name for w in words):
            return COST_BENCHMARKS[group]
    return COST_BENCHMARKS["other"]


def monthly_payroll(headcount: int) -> int:
    return MIN_WAGE_HOURLY_2026 * MONTHLY_HOURS * max(headcount, 0)
