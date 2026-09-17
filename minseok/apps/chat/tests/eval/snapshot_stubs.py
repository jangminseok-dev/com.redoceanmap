"""평가 러너용 고정 스냅샷 스텁 — 허브 포트를 결정론 데이터로 채운다.

원칙: LLM만 진짜로 부르고, 데이터는 전부 고정한다.
- 상권 요약·업종 코드는 `snapshot/market_snapshot.json`(백엔드 PC에서
  scripts/dump_chat_eval_snapshot.py로 덤프)이 있으면 실데이터, 없으면 내장 합성본.
- 팩트 통계·점수·인사이트는 trdar_code 시드 합성 — phase2 환각 판정은
  "답변 숫자가 컨텍스트에 있었는가"만 보므로 수치의 실제성이 필요 없다.
  (전 상권 × 전 업종 팩트를 덤프하면 스냅샷이 수십 MB가 되는 것을 회피)
- 상권 DB가 분기마다 갱신돼도 골든셋 정답이 흔들리지 않는다(스냅샷 고정).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from chat.domain.entities.conversation_entity import Conversation, Message
from hub.app.dtos.commercial_data_dto import (
    AreaInfo,
    AreaInsight,
    AreaRankingInfo,
    AreaRawStat,
    AreaScoreComponent,
    AreaScoreInfo,
    AreaSummary,
    AreaTraitRow,
    PermitChurnInfo,
    ServiceCode,
)
from hub.app.dtos.gemini_dto import GeminiAnswerResponse
from hub.app.dtos.news_dto import NewsHit
from hub.app.dtos.stock_analysis_dto import StockAnalysisResult

_SNAPSHOT_PATH = Path(__file__).parent / "snapshot" / "market_snapshot.json"
_NOW = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)

# 합성 상권 — 골든셋 market_region 20문항의 지명을 전부 커버한다.
# (trdar_code, 상권명, 자치구, 행정동, 월매출합계(원))
_SYN_AREAS = [
    (3110001, "성수동2가", "성동구", "성수2가1동", 9_200_000_000),
    (3110002, "성수동1가", "성동구", "성수1가2동", 6_100_000_000),
    (3110003, "홍대 걷고싶은거리", "마포구", "서교동", 12_400_000_000),
    (3110004, "홍대입구역", "마포구", "서교동", 10_800_000_000),
    (3110005, "강남역", "강남구", "역삼1동", 21_500_000_000),
    (3110006, "강남대로", "강남구", "역삼1동", 15_300_000_000),
    (3110007, "연남동", "마포구", "연남동", 5_400_000_000),
    (3110008, "망원동", "마포구", "망원1동", 3_800_000_000),
    (3110009, "서촌", "종로구", "청운효자동", 2_900_000_000),
    (3110010, "익선동", "종로구", "종로1·2·3·4가동", 3_200_000_000),
    (3110011, "성신여대입구역", "성북구", "동선동", 4_600_000_000),
    (3110012, "미아사거리역", "강북구", "미아동", 5_100_000_000),
    (3110013, "노원역", "노원구", "상계2동", 6_800_000_000),
    (3110014, "왕십리역", "성동구", "행당1동", 7_200_000_000),
    (3110015, "건대입구역", "광진구", "화양동", 9_800_000_000),
    (3110016, "신촌역", "서대문구", "신촌동", 8_400_000_000),
    (3110017, "이태원", "용산구", "이태원1동", 6_300_000_000),
    (3110018, "문래동3가", "영등포구", "문래동", 2_400_000_000),
    (3110019, "잠실역", "송파구", "잠실6동", 13_600_000_000),
    (3110020, "여의도", "영등포구", "여의동", 11_900_000_000),
    (3110021, "종로3가역", "종로구", "종로1·2·3·4가동", 7_600_000_000),
    (3110022, "압구정로데오역", "강남구", "압구정동", 8_900_000_000),
    (3110023, "마곡나루역", "강서구", "마곡동", 4_100_000_000),
    (3110024, "명동", "중구", "명동", 16_700_000_000),
    (3110025, "을지로3가", "중구", "을지로동", 5_700_000_000),
]

_SYN_SERVICE_CODES = [
    ("CS100001", "한식음식점"), ("CS100002", "중식음식점"), ("CS100003", "일식음식점"),
    ("CS100004", "양식음식점"), ("CS100005", "제과점"), ("CS100006", "패스트푸드점"),
    ("CS100007", "치킨전문점"), ("CS100008", "분식전문점"), ("CS100009", "호프-간이주점"),
    ("CS100010", "커피-음료"), ("CS200001", "편의점"), ("CS200002", "화장품"),
    ("CS200003", "의류"), ("CS200004", "미용실"), ("CS200005", "네일숍"),
    ("CS200006", "스터디카페-독서실"), ("CS200007", "키즈카페"),
]

_SYN_QUARTER = 20261

_CHANGE_NAMES = ("다이나믹", "상권확장", "정체", "상권축소")


def load_market_snapshot() -> tuple[list[AreaInfo], dict[int, int], int, list[ServiceCode], bool]:
    """(areas, sales_by_code, latest_quarter, service_codes, is_real) 반환."""
    if _SNAPSHOT_PATH.exists():
        data = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        areas = [
            AreaInfo(
                trdar_code=a["trdar_code"], trdar_name=a["trdar_name"],
                district_name=a["district_name"], adm_dong_name=a["adm_dong_name"],
                lat=a["lat"], lng=a["lng"],
            )
            for a in data["areas"]
        ]
        sales = {a["trdar_code"]: a["sales"] for a in data["areas"] if a.get("sales")}
        codes = [ServiceCode(code=c["code"], name=c["name"]) for c in data["service_codes"]]
        return areas, sales, data["latest_quarter"], codes, True
    areas = [
        AreaInfo(trdar_code=c, trdar_name=n, district_name=d, adm_dong_name=g,
                 lat=37.5, lng=127.0)
        for c, n, d, g, _ in _SYN_AREAS
    ]
    sales = {c: s for c, _, _, _, s in _SYN_AREAS}
    codes = [ServiceCode(code=c, name=n) for c, n in _SYN_SERVICE_CODES]
    return areas, sales, _SYN_QUARTER, codes, False


def _seed(code: int) -> int:
    return (code * 2654435761) % 1000  # 결정론 시드 — 실행마다 같은 수치


def synthetic_raw_stat(code: int) -> AreaRawStat:
    s = _seed(code)
    store = 40 + s % 160
    closure = round(1.0 + (s % 40) / 10, 1)
    opening = round(1.5 + (s % 35) / 10, 1)
    total_fp = (30 + s % 60) * 100_000
    return AreaRawStat(
        has_sales=True,
        monthly_sales_amount=(30 + s % 90) * 10_000_000,
        weekday_sales_amount=(30 + s % 90) * 10_000_000 * (55 + s % 20) // 100,
        has_store=True, store_count=store,
        closure_rate=closure, closure_store_count=max(1, int(store * closure / 100)),
        opening_rate=opening, opening_store_count=max(1, int(store * opening / 100)),
        franchise_store_count=store * (10 + s % 30) // 100,
        similar_industry_store_count=store // 3,
        has_fp=True, total_floating_pop=total_fp,
        age_10_floating_pop=total_fp * (5 + s % 5) // 100,
        age_20_floating_pop=total_fp * (20 + s % 15) // 100,
        age_30_floating_pop=total_fp * (20 + s % 10) // 100,
        age_40_floating_pop=total_fp * 18 // 100,
        age_50_floating_pop=total_fp * 15 // 100,
        age_60_plus_floating_pop=total_fp * 10 // 100,
        time_00_06_floating_pop=total_fp * 8 // 100,
        time_06_11_floating_pop=total_fp * (15 + s % 10) // 100,
        time_11_14_floating_pop=total_fp * (18 + s % 8) // 100,
        time_14_17_floating_pop=total_fp * (16 + s % 8) // 100,
        time_17_21_floating_pop=total_fp * (20 + s % 10) // 100,
        time_21_24_floating_pop=total_fp * 10 // 100,
        has_cc=True, change_indicator_name=_CHANGE_NAMES[s % 4],
        operating_months_avg=70 + s % 60, region_operating_months_avg=100,
        closure_months_avg=30 + s % 30, region_closure_months_avg=45,
    )


def synthetic_score(code: int) -> AreaScoreInfo | None:
    s = _seed(code)
    if s % 2:
        return None  # 산출 불가 상권 라인 생략 경로도 평가에 포함
    total = round(40 + s % 30 + 0.5, 1)
    grade = "우수" if total >= 60 else "보통" if total >= 45 else "주의"
    return AreaScoreInfo(
        total=total, grade=grade,
        components=(
            AreaScoreComponent(key="closure_stability", name="폐업 안정성",
                               score=round(30 + s % 60 + 0.3, 1),
                               value=round((s % 50) / 10, 1), benchmark=2.7),
            AreaScoreComponent(key="sales_level", name="점포당 매출 수준",
                               score=round(35 + s % 50 + 0.7, 1),
                               value=float(800 + s % 2400), benchmark=1656.0),
            AreaScoreComponent(key="persistence", name="영업 지속성",
                               score=round(25 + s % 55 + 0.1, 1),
                               value=float(70 + s % 60), benchmark=100.0),
        ),
    )


def synthetic_insights(code: int) -> tuple[AreaInsight, ...] | None:
    s = _seed(code)
    if s % 3 == 0:
        return None  # 인사이트 없는 상권 라인 생략 경로도 평가에 포함
    demand = "오피스형" if s % 2 else "주거형"
    return (
        AreaInsight(key="demand_type", tone="neutral",
                    text=f"직장인 중심 {demand} 상권입니다" if s % 2
                    else f"거주민 중심 {demand} 상권입니다"),
        AreaInsight(key="avg_ticket", tone="neutral",
                    text=f"건당 평균 결제액 {round(0.8 + (s % 30) / 10, 1)}만원"),
        AreaInsight(key="customer_age", tone="neutral",
                    text=f"{20 + (s % 3) * 10}대가 핵심 고객층입니다"),
    )


def synthetic_permit_churn(code: int) -> PermitChurnInfo | None:
    s = _seed(code)
    if s % 4 == 0:
        return None  # 인허가가 안 붙은 상권 — 라인 생략 경로도 평가에 포함
    opened = 3 + s % 22
    return PermitChurnInfo(
        months=12,
        opened=opened,
        closed=2 + (s * 3) % 20,
        active=60 + s % 240,
    )


# --- 기록형 스텁 포트 (기존 test_chat_interactor 스텁의 스냅샷 판) ---


class SnapshotMarket:
    """CommercialDataPort — 요약·업종은 스냅샷, 팩트·점수·인사이트는 시드 합성."""

    def __init__(self) -> None:
        areas, sales, quarter, codes, self.is_real = load_market_snapshot()
        self._areas, self._sales, self._quarter, self._codes = areas, sales, quarter, codes
        self.summary_calls = 0

    @property
    def area_map(self) -> dict[int, AreaInfo]:
        return {a.trdar_code: a for a in self._areas}

    async def get_area_summary(self) -> AreaSummary:
        self.summary_calls += 1
        return AreaSummary(areas=self._areas, latest_quarter=self._quarter,
                           sales_by_code=self._sales)

    async def get_service_codes(self) -> list[ServiceCode]:
        return self._codes

    async def get_area_raw_stats(self, codes, service_code, quarter):
        return {c: synthetic_raw_stat(c) for c in codes}

    async def get_area_scores(self, trdar_codes):
        return {c: s for c in trdar_codes if (s := synthetic_score(c)) is not None}

    async def get_area_insights(self, trdar_codes, service_code=None):
        return {c: i for c in trdar_codes if (i := synthetic_insights(c)) is not None}

    async def get_area_permit_churn(self, trdar_codes, months=12):
        return {c: p for c in trdar_codes if (p := synthetic_permit_churn(c)) is not None}

    async def get_area_traits(self, service_scope=None):
        # 성격형 질문 결정론 랭킹(2026-09-17, MN03·04·06·07·09)용 — 요약 스냅샷에서 시드 합성(다른 합성과 동일 규칙)
        rows = []
        for a in self._areas:
            s = _seed(a.trdar_code)
            h = (a.trdar_code * 2654435761) % 1_000_003  # 인구·시설용 넓은 시드 — 동률이 흔하면 결론 오라클이 순서 오류를 못 잡는다
            sales = self._sales.get(a.trdar_code)
            month = (sales // 3) if sales else None
            rows.append(AreaTraitRow(
                trdar_code=a.trdar_code, trdar_name=a.trdar_name,
                district_name=a.district_name, dong_name=a.adm_dong_name,
                store_count=150 + s % 300, area_store_count=400 + s % 800,  # 업종 범위 합계 수준 — 점포당 금액이 현실 범위에 오게
                monthly_sales=month, monthly_sales_count=(month // (8_000 + s % 20_000)) if month else None,
                lunch_sales=month * (15 + s % 25) // 100 if month else None,
                dinner_sales=month * (20 + s % 20) // 100 if month else None,
                night_sales=month * (3 + s % 15) // 100 if month else None,
                weekend_sales=month * (20 + s % 30) // 100 if month else None,
                weekday_sales=month * (50 + s % 30) // 100 if month else None,
                age_sales=tuple(month * p // 100 for p in (3, 20 + s % 15, 25, 20, 15, 10)) if month else None,
                working_pop=1_000 + h % 150_000, floating_pop=3_000_000 + h * 7 % 9_000_000,
                night_floating_pop=300_000 + h * 13 % 1_500_000, total_households=500 + h * 3 % 9_000,
                apartment_households=h * 11 % 5_000, university_count=h % 7, subway_station_count=h % 3,
                child_facility_count=h % 5,
            ))
        return rows

    async def get_area_ranking(self, service_code=None):
        # 조건 질의 결정론 라우팅(I-14, MN11)용 — 요약 스냅샷에서 시드 합성(다른 합성과 동일 규칙)
        rows = []
        for a in self._areas:
            s = a.trdar_code % 100
            sales = self._sales.get(a.trdar_code)
            stores = 5 + s % 60
            rows.append(AreaRankingInfo(
                trdar_code=a.trdar_code, trdar_name=a.trdar_name,
                district_name=a.district_name, dong_name=a.adm_dong_name,
                monthly_sales=sales, store_count=stores,
                sales_per_store=(sales // stores) if sales else None,
                closure_rate=float(s % 7), change_indicator_name=None,
            ))
        return rows


class SnapshotStocks:
    """StockAnalysisPort — 질의를 기록하고 시드 합성 지표를 돌려준다."""

    _KR_SYMBOLS = {
        "삼성전자": "005930", "삼전": "005930", "삼성": "005930",
        "SK하이닉스": "000660", "하이닉스": "000660", "하닉": "000660",
        "카카오": "035720", "네이버": "035420", "NAVER": "035420",
        "현대차": "005380", "현대자동차": "005380",
        "LG에너지솔루션": "373220", "LG엔솔": "373220",
        "셀트리온": "068270", "삼성바이오로직스": "207940",
        "기아": "000270", "기아차": "000270",
        "포스코홀딩스": "005490", "POSCO홀딩스": "005490", "포스코": "005490",
        "한화에어로스페이스": "012450", "두산에너빌리티": "034020",
        "KB금융": "105560", "크래프톤": "259960", "에코프로": "086520",
    }

    def __init__(self) -> None:
        self.queries: list[str] = []

    async def analyze(self, query: str) -> StockAnalysisResult:
        self.queries.append(query)
        symbol = self._KR_SYMBOLS.get(query, query)
        s = sum(ord(ch) for ch in symbol) % 100
        korean = len(symbol.split(".")[0]) == 6 and symbol.split(".")[0].isdigit()
        price = float((50 + s) * 1000) if korean else float(120 + s)
        return StockAnalysisResult(
            symbol=symbol, price=price,
            direction="NEUTRAL", confidence=round(0.1 + s / 500, 2),
            sentiment=round((s - 50) / 100, 2),
            sentiment_label="긍정" if s >= 50 else "부정",
            rsi=round(35.0 + s / 2, 1),
            ma20=round(price * 0.97, 2), ma50=round(price * 0.93, 2),
            support=round(price * 0.88, 2), resistance=round(price * 1.09, 2),
            headlines=[],
            atr_pct=round(0.015 + s / 4000, 4), bb_percent_b=round(0.2 + s / 200, 2),
            volume_ratio=round(0.8 + s / 100, 1), obv_slope=float(s % 3 - 1),
            momentum_12_1=round((s - 40) / 400, 3),
            reference_up_signal=False,  # 라인 생략 경로 고정 — 컨텍스트 단순화
            # 매물대 — 시드 기준 1/4은 산출 불가로 둬서 라인 생략 경로도 평가에 포함한다.
            # POC를 현재가 아래에 둬 '현재가는 그 위'가 나오게 고정(서술 일관성 확인용).
            **({} if s % 4 == 0 else dict(
                volume_poc_low=round(price * 0.90, 2),
                volume_poc_high=round(price * 0.94, 2),
                volume_poc_share=round(0.10 + (s % 25) / 100, 2),
                volume_price_position="above",
            )),
        )


class SnapshotNewsSearch:
    """NewsSearchPort — market_news(코퍼스 횡단)만 고정 히트, 종목 검색은 빈 결과."""

    _HITS = [
        ("업황 회복 기대감에 관련 업종 투자 심리 개선", 0.6, "실적"),
        ("주요 기관, 하반기 시장 전망 보고서 발간", 0.0, "기타"),
        ("금리 방향을 둘러싼 관망세 지속", -0.2, "거시"),
        ("수출 지표 개선에 대형주 중심 반등", 0.4, "거시"),
        ("업계 재편 소식에 중소형주 변동성 확대", -0.5, "산업"),
    ]

    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None, int]] = []

    async def search(self, query: str, ticker: str | None = None, limit: int = 5):
        self.calls.append((query, ticker, limit))
        if ticker is not None:
            return []
        return [
            NewsHit(title=t, ticker=None, published_at=_NOW,
                    sentiment=sent, event_type=ev, source="평가스냅샷")
            for t, sent, ev in self._HITS[:limit]
        ]


class SnapshotMarketNews:
    """MarketNewsSearchPort — 기사 블록 생략 경로 고정(빈 결과)."""

    async def search(self, query: str, limit: int = 4):
        return []


class SnapshotGemini:
    """GeminiAnswerPort — 외부 API를 부르지 않는다(라우팅만 평가)."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> GeminiAnswerResponse:
        self.prompts.append(prompt)
        return GeminiAnswerResponse(answer="일반 질문 답변(평가 스텁)", model="eval-stub")


class SnapshotRecorder:
    async def record(self, conversation_id: int, areas) -> None:
        return None


class SnapshotForecast:
    async def forecast(self, ticker: str):
        return None  # 과거 통계 라인 생략 경로 고정


class SnapshotFundamentals:
    async def latest_insights(self, ticker: str):
        return []  # 펀더멘털 라인 생략 경로 고정


class SnapshotConversations:
    """ConversationRepository — 케이스별 새 대화. multiturn은 직전 추천을 시딩한다."""

    def __init__(self, history: list[Message] | None = None) -> None:
        self._history = history or []
        self._next_id = 9000

    async def create_conversation(self, user_id: int | None = None) -> Conversation:
        self._next_id += 1
        return Conversation(id=self._next_id, created_at=_NOW, user_id=user_id)

    async def add_message(self, conversation_id: int, role: str, content: str,
                          payload: dict | None = None) -> Message:
        msg = Message(id=len(self._history) + 1, conversation_id=conversation_id,
                      role=role, content=content, created_at=_NOW, payload=payload)
        self._history.append(msg)
        return msg

    async def get_messages(self, conversation_id: int, limit: int = 20) -> list[Message]:
        return list(self._history)

    async def get_conversation(self, conversation_id: int) -> Conversation | None:
        return Conversation(id=conversation_id, created_at=_NOW, user_id=None)

    async def list_conversations(self, user_id: int, limit: int = 30):
        return []


class SnapshotFinance:
    """AreaFinancePort 고정 스텁 — 시드 결정론 산술(엔진 정본은 market, 여기서는 계약 DTO만 만든다)."""

    RENT_PER_SQM = 45_000
    COST_RATIO = 0.35
    LOAN_RATE = 4.5

    def __init__(self) -> None:
        self.requests: list = []

    async def plan(self, request):
        from hub.app.dtos.area_finance_dto import AreaFinancePlanInfo, FinanceInputItem

        self.requests.append(request)
        rent = request.monthly_rent or int(self.RENT_PER_SQM * (request.area_sqm or 33))
        deposit = request.deposit if request.deposit is not None else rent * 10
        startup = request.startup_cost if request.startup_cost is not None else 80_000_000
        payroll = 10_320 * 209 * (request.headcount or 0)
        capex = startup + deposit + (request.key_money or 0)
        opex = rent + payroll
        gap = max(0, capex + opex * 3 - request.equity)
        loan = max(request.desired_loan or 0, gap)
        fixed = opex + round(loan * self.LOAN_RATE / 100 / 12)
        bep = round(fixed / (1 - self.COST_RATIO))
        sales = 12_000_000 + (_seed(request.trdar_code) % 9) * 1_000_000
        profit = round(sales * (1 - self.COST_RATIO) - fixed)
        cash = max(0, request.equity + loan - capex)
        runway = None if profit >= 0 else round(cash / abs(profit), 1)
        headline = (f"자기자본 {request.equity // 10_000:,}만원(입력)·월세 {rent // 10_000:,}만원"
                    f"({'입력' if request.monthly_rent else '권역 평균, 33㎡ 가정'})·창업비용 {startup // 10_000:,}만원(공정위 중앙값)"
                    f"으로 계산하면 손익분기 월매출은 {bep // 10_000:,}만원이에요. 점포당 월매출 {sales // 10_000:,}만원이면"
                    f" 달성률 {sales / bep:.0%}. 부족 자금 {gap // 10_000:,}만원이 필요해요."
                    + (f" 적자가 이어지면 약 {runway:.0f}개월 버틸 수 있어요." if runway else ""))
        return AreaFinancePlanInfo(
            trdar_code=request.trdar_code, trdar_name="", service_code=request.service_code, service_name="",
            headline=headline, assumption_note="가정: 보증금은 월세 10개월분 가정 · 1인 운영 가정 · 이자만 반영",
            inputs=(FinanceInputItem("equity", request.equity, "input", ""), FinanceInputItem("monthly_rent", rent, "input" if request.monthly_rent else "area_avg", "")),
            capex=capex, funding_gap=gap, loan=loan, bep_monthly_sales=bep, attainment=round(sales / bep, 2),
            monthly_profit=profit, runway_months=runway, stress_runway=((1.0, runway), (2.0, runway)),
            expected_monthly_sales=sales, rent_level="zone",
        )


def seeded_conversations(market: SnapshotMarket, regions: tuple[str, ...],
                         per_region: int = 2) -> tuple[SnapshotConversations, tuple[int, ...]]:
    """multiturn 시딩 — 지역 어간이 걸리는 상권 상위 N개를 직전 추천 payload로 넣는다."""
    from chat.domain.services.eval_scorer import _stem  # 같은 어간 규칙 재사용

    codes: list[int] = []
    areas, sales, *_ = load_market_snapshot()
    ranked = sorted(areas, key=lambda a: sales.get(a.trdar_code, 0), reverse=True)
    for region in regions:
        stem = _stem(region)
        picked = [
            a.trdar_code for a in ranked
            if stem and (stem in a.trdar_name or stem in a.district_name
                         or stem in a.adm_dong_name)
        ][:per_region]
        codes.extend(picked)
    area_map = market.area_map
    history = [
        Message(id=1, conversation_id=1, role="user",
                content=f"{' '.join(regions)} 상권 어때?", created_at=_NOW, payload=None),
        Message(id=2, conversation_id=1, role="assistant", content="상권 추천",
                created_at=_NOW,
                payload={"recommendations": [
                    {"id": str(c), "name": area_map[c].trdar_name} for c in codes
                ]}),
    ]
    return SnapshotConversations(history=history), tuple(codes)
