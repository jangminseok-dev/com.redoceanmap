"""업종군별 원가율·영업이익률 벤치마크 — 결정론 상수(KOSIS API 적재 안 함, FINANCE_ENGINE D3).

값은 소상공인실태조사 발표 표와 대조해 교체한다 — 대조 전까지 잠정치이며 source에 "잠정"을 남긴다.
B8 회수기간과 같은 방식: 가정치를 답변에 출처와 함께 병기한다(외식 이익률은 확인된 출처 — EATOUT_MARGIN).
"""
from __future__ import annotations

from dataclasses import dataclass

MIN_WAGE_HOURLY_2026 = 10_320   # 2026년 최저임금 시급(2025-07 고시)
MONTHLY_HOURS = 209             # 주 40시간 + 주휴 환산 월 근로시간
DEFAULT_SHOP_SQM = 33.0         # 면적 미입력 시 10평 가정
DEPOSIT_MONTHS = 10             # 보증금 미입력 시 월세 10개월분 가정
WORKING_CAPITAL_MONTHS = 3      # 개업 후 버틸 운전자금(고정비 N개월분)
DEFAULT_LOAN_RATE = 4.5         # ECOS 미적재 시 연 %
# 카드 결제 수수료(VAN 포함) — 매출에 비례하는 변동비로 원가율에 더한다(2026-09-17 추가, 가정치).
# 영세·중소 가맹점 우대 수수료가 0.4~1.45%이고 VAN·간편결제 비용이 붙어 1.5%로 둔다. 현금·계좌이체 매출 비중은 무시.
CARD_FEE_RATIO = 0.015
DEFAULT_WORKERS = 1             # 인원을 말하지 않으면 점주 본인 1인분 인건비를 넣는다(0으로 두면 이익이 점주 노동값까지 포함됐다)
MARGIN_WARN_FACTOR = 1.5        # 계산된 영업이익률이 업종 벤치마크의 이 배수를 넘으면 과대 추정 경고

_SOURCE = "소상공인실태조사 2024(중기부·통계청) 대조 전 잠정치"

# 외식업(음식점·카페·주점) 영업이익률 — 농촌경제연구원 「2024년 외식업체 경영실태조사」 8.7%
# (업체당 연매출 2억 5,526만원·영업이익 2,220만원, 2020년 12.1%에서 하락). 조사가 세 군을 나눠 발표하지
# 않아 한 값으로 둔다(2026-09-17 교체 — 이전 잠정치 12~14%는 출처 없이 1.4~1.6배 높았다).
# 이익률 출처가 확인된 업종군은 이것뿐이다 — 나머지 군의 margin_ratio는 여전히 잠정치.
EATOUT_MARGIN = 0.087
EATOUT_MARGIN_SOURCE = "농촌경제연구원 외식업체 경영실태조사 2024"
VERIFIED_MARGIN_GROUPS = frozenset({"food", "cafe", "pub"})


@dataclass(frozen=True)
class CostBenchmark:
    group: str
    label: str
    cost_ratio: float     # 매출 대비 재료비(변동비) 비율
    margin_ratio: float   # 영업이익률
    source: str


COST_BENCHMARKS: dict[str, CostBenchmark] = {
    "food": CostBenchmark("food", "음식점", 0.38, EATOUT_MARGIN, _SOURCE),
    "cafe": CostBenchmark("cafe", "카페·음료", 0.30, EATOUT_MARGIN, _SOURCE),
    "pub": CostBenchmark("pub", "주점", 0.35, EATOUT_MARGIN, _SOURCE),
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
