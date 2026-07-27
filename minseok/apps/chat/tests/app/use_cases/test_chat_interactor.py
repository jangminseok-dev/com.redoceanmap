"""ChatInteractor 테스트 — 스텁 포트 + 모듈 네임스페이스 LLM 교체.

llm_orchestrator는 전역 싱글턴이지만 chat_interactor가 모듈 전역 이름으로 바인딩하므로
monkeypatch로 모듈 네임스페이스의 이름만 갈아끼운다(다른 모듈 무영향, teardown 자동).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from chat.app.exceptions import ConversationNotFoundError
from chat.app.use_cases.chat_interactor import ChatInteractor
from chat.domain.entities.conversation_entity import Conversation, Message
from hub.app.dtos.commercial_data_dto import (
    AreaInfo,
    AreaInsight,
    AreaRawStat,
    AreaScoreComponent,
    AreaScoreInfo,
    AreaSummary,
    ServiceCode,
)
from chat.domain.services.verdict import strength, verdict
from hub.app.dtos.fundamental_dto import FundamentalInsightItem
from hub.app.dtos.market_news_dto import MarketNewsHit
from hub.app.dtos.news_dto import NewsHit
from hub.app.dtos.stock_analysis_dto import StockAnalysisResult
from hub.app.dtos.stock_forecast_dto import StockForecastSummary
from hub.app.ports.output.stock_analysis_port import StockAnalysisUnavailable

_NOW = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)

INTENT_STOCK = '{"intent": "stock", "stock_query": "삼성전자"}'
INTENT_STOCK_NO_QUERY = '{"intent": "stock", "stock_query": ""}'
INTENT_MARKET_NEWS = '{"intent": "market_news", "stock_query": ""}'
INTENT_MARKET = '{"intent": "market", "stock_query": ""}'
INTENT_GENERAL = '{"intent": "general", "stock_query": ""}'
PHASE1_JSON = '{"service_code": "CS100010", "service_name": "커피-음료", "trdar_codes": [1000001]}'
PHASE1_EMPTY = '{"service_code": "CS100010", "service_name": "커피-음료", "trdar_codes": []}'
PHASE2_JSON = '{"text": "상권 요약", "areas": [{"trdar_code": 1000001, "reason": "추천 이유"}]}'


class _StubLLM:
    def __init__(self, responses: list[str]):
        self.calls: list[tuple[str, dict]] = []
        self._responses = list(responses)

    async def orchestrate(self, prompt: str, **kwargs) -> str:
        self.calls.append((prompt, kwargs))
        return self._responses.pop(0)


class _StubConversations:
    def __init__(self, history: list[Message] | None = None,
                 conversation: Conversation | None = None):
        self._history = history or []
        self._conversation = conversation
        self.saved: list[tuple[str, str]] = []
        self.payloads: list[dict | None] = []
        self.created_user_ids: list[int | None] = []
        self._next_id = 100

    async def create_conversation(self, user_id: int | None = None) -> Conversation:
        self._next_id += 1
        self.created_user_ids.append(user_id)
        return Conversation(id=self._next_id, created_at=_NOW, user_id=user_id)

    async def add_message(self, conversation_id: int, role: str, content: str,
                          payload: dict | None = None) -> Message:
        self.saved.append((role, content))
        self.payloads.append(payload)
        return Message(id=len(self.saved), conversation_id=conversation_id,
                       role=role, content=content, created_at=_NOW, payload=payload)

    async def get_messages(self, conversation_id: int, limit: int = 20) -> list[Message]:
        return self._history

    async def get_conversation(self, conversation_id: int) -> Conversation | None:
        return self._conversation

    async def list_conversations(self, user_id: int, limit: int = 30):
        return []


class _StubStocks:
    def __init__(self, result: StockAnalysisResult | None = None, fail: bool = False):
        self.result = result
        self.fail = fail
        self.queries: list[str] = []

    async def analyze(self, query: str) -> StockAnalysisResult:
        self.queries.append(query)
        if self.fail:
            raise StockAnalysisUnavailable("종목을 찾지 못했습니다: X.")
        return self.result


class _StubNewsSearch:
    def __init__(self, hits: list[NewsHit] | None = None):
        self.hits = hits or []
        self.calls: list[tuple[str, str | None, int]] = []

    async def search(self, query: str, ticker: str | None = None, limit: int = 5) -> list[NewsHit]:
        self.calls.append((query, ticker, limit))
        return self.hits


class _StubForecast:
    def __init__(self, summary: StockForecastSummary | None = None):
        self.summary = summary
        self.calls: list[str] = []

    async def forecast(self, ticker: str) -> StockForecastSummary | None:
        self.calls.append(ticker)
        return self.summary


class _StubFundamentals:
    def __init__(self, insights: list[FundamentalInsightItem] | None = None):
        self.insights = insights or []
        self.calls: list[str] = []

    async def latest_insights(self, ticker: str) -> list[FundamentalInsightItem]:
        self.calls.append(ticker)
        return self.insights


class _StubMarket:
    def __init__(self, scores: dict[int, AreaScoreInfo] | None = None,
                 insights: dict[int, tuple[AreaInsight, ...]] | None = None,
                 raw: AreaRawStat | None = None):
        self.summary_calls = 0
        self.scores = scores or {}
        self.score_calls: list[list[int]] = []
        self.insights = insights or {}
        self.insight_calls: list[tuple[list[int], str | None]] = []
        self.raw = raw

    async def get_area_summary(self) -> AreaSummary:
        self.summary_calls += 1
        area = AreaInfo(trdar_code=1000001, trdar_name="테스트상권", district_name="강남구",
                        adm_dong_name="역삼동", lat=37.5, lng=127.0)
        return AreaSummary(areas=[area], latest_quarter=20254, sales_by_code={1000001: 100_000_000})

    async def get_service_codes(self) -> list[ServiceCode]:
        return [ServiceCode(code="CS100010", name="커피-음료")]

    async def get_area_raw_stats(self, codes, service_code, quarter):
        return {c: (self.raw or _raw_stat()) for c in codes}

    async def get_area_scores(self, trdar_codes):
        self.score_calls.append(list(trdar_codes))
        return self.scores

    async def get_area_insights(self, trdar_codes, service_code=None):
        self.insight_calls.append((list(trdar_codes), service_code))
        return self.insights


class _StubMarketNews:
    def __init__(self, hits: list[MarketNewsHit] | None = None):
        self.hits = hits or []
        self.calls: list[tuple[str, int]] = []

    async def search(self, query: str, limit: int = 4) -> list[MarketNewsHit]:
        self.calls.append((query, limit))
        return self.hits


class _StubGemini:
    def __init__(self, fail=False):
        self.fail = fail
        self.prompts = []

    async def generate(self, prompt):
        from hub.app.dtos.gemini_dto import GeminiAnswerResponse
        from hub.app.ports.output.gemini_answer_port import GeminiAnswerError

        self.prompts.append(prompt)
        if self.fail:
            raise GeminiAnswerError("키 미설정")
        return GeminiAnswerResponse(answer="제미나이 답변", model="gemini-test")


class _StubRecorder:
    def __init__(self):
        self.recorded: list = []

    async def record(self, conversation_id: int, areas) -> None:
        self.recorded.append((conversation_id, areas))


def _raw_stat(**overrides) -> AreaRawStat:
    base = dict(
        has_sales=False, monthly_sales_amount=None, weekday_sales_amount=None,
        has_store=False, store_count=None, closure_rate=None, opening_rate=None,
        franchise_store_count=None,
        has_fp=False, total_floating_pop=None,
        age_10_floating_pop=None, age_20_floating_pop=None, age_30_floating_pop=None,
        age_40_floating_pop=None, age_50_floating_pop=None, age_60_plus_floating_pop=None,
        time_00_06_floating_pop=None, time_06_11_floating_pop=None, time_11_14_floating_pop=None,
        time_14_17_floating_pop=None, time_17_21_floating_pop=None, time_21_24_floating_pop=None,
        has_cc=False, change_indicator_name=None, operating_months_avg=None,
        region_operating_months_avg=None,
    )
    return AreaRawStat(**{**base, **overrides})


def _analysis(**overrides) -> StockAnalysisResult:
    base = dict(
        symbol="005930", price=90000.0, direction="NEUTRAL", confidence=0.1,
        sentiment=0.4, sentiment_label="긍정", rsi=45.0, ma20=88000.0, ma50=85000.0,
        support=80000.0, resistance=95000.0, headlines=["삼성전자 실적 발표"],
        atr_pct=0.025, bb_percent_b=0.15, volume_ratio=1.8, obv_slope=0.5,
        momentum_12_1=0.22, reference_up_signal=True,
    )
    return StockAnalysisResult(**{**base, **overrides})


def _hit(**overrides) -> NewsHit:
    base = dict(title="반도체 업황 회복 조짐", ticker="005930.KS",
                published_at=_NOW, sentiment=0.7, event_type="실적", source="테스트")
    return NewsHit(**{**base, **overrides})


def _area_score() -> AreaScoreInfo:
    return AreaScoreInfo(
        total=59.6, grade="보통",
        components=(
            AreaScoreComponent(key="sales_growth", name="매출 성장",
                               score=91.9, value=21.9, benchmark=5.2),
            AreaScoreComponent(key="persistence", name="영업 지속성",
                               score=16.1, value=76.0, benchmark=115.0),
        ),
    )


def _build(monkeypatch, llm_responses, *, stocks=None, news=None, conversations=None,
           market=None, market_news=None, gemini=None, forecaster=None, fundamentals=None):
    llm = _StubLLM(llm_responses)
    monkeypatch.setattr("chat.app.use_cases.chat_interactor.llm_orchestrator", llm)
    market, recorder = market or _StubMarket(), _StubRecorder()
    conversations = conversations or _StubConversations()
    stocks = stocks or _StubStocks(result=_analysis())
    news = news or _StubNewsSearch()
    market_news = market_news or _StubMarketNews()
    gemini = gemini or _StubGemini()
    forecaster = forecaster or _StubForecast()
    fundamentals = fundamentals or _StubFundamentals()
    interactor = ChatInteractor(
        market=market, recorder=recorder, conversations=conversations,
        stocks=stocks, news=news, market_news=market_news, gemini=gemini,
        forecaster=forecaster, fundamentals=fundamentals,
    )
    return interactor, llm, dict(market=market, recorder=recorder,
                                 conversations=conversations, stocks=stocks, news=news,
                                 market_news=market_news, gemini=gemini, forecaster=forecaster,
                                 fundamentals=fundamentals)


# --- phase0 3분류 라우팅 ---

async def test_stock_의도면_분석_포트를_호출하고_카드를_반환한다(monkeypatch):
    interactor, _, stubs = _build(monkeypatch, [INTENT_STOCK, "주식 서술"])
    result = await interactor.ask("삼성전자 어때?")
    assert stubs["stocks"].queries == ["삼성전자"]
    assert result.stock is not None and result.stock.symbol == "005930"
    assert result.text == "주식 서술"


async def test_market_news_의도면_뉴스_검색을_코퍼스_횡단으로_호출한다(monkeypatch):
    news = _StubNewsSearch(hits=[_hit()])
    interactor, _, _ = _build(monkeypatch, [INTENT_MARKET_NEWS, "업황 서술"], news=news)
    result = await interactor.ask("반도체 업황 어때?")
    assert news.calls == [("반도체 업황 어때?", None, 8)]
    assert result.text == "업황 서술" and result.recommendations == []


async def test_market_의도면_기존_상권_경로가_그대로_동작한다(monkeypatch):  # 무손상 회귀
    interactor, _, stubs = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON])
    result = await interactor.ask("성수동 카페 어때?")
    assert stubs["market"].summary_calls == 1
    assert len(result.recommendations) == 1
    assert result.recommendations[0].name == "테스트상권"
    assert len(stubs["recorder"].recorded) == 1


async def test_지역_미언급_후속질문은_직전_추천_상권을_이어받는다(monkeypatch):
    # "길음시장…" 추천 뒤 "카페 창업을 한다면?" — phase1이 상권을 못 이어받아
    # 후보가 비어도 직전 추천 payload에서 코드를 복원해 422를 막는다.
    conversations = _StubConversations(history=[
        Message(id=1, conversation_id=100, role="user", content="길음역 상권 어때?",
                created_at=_NOW, payload=None),
        Message(id=2, conversation_id=100, role="assistant", content="길음시장 추천",
                created_at=_NOW,
                payload={"recommendations": [{"id": "1000001", "name": "테스트상권"}]}),
    ])
    interactor, _, _ = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_EMPTY, PHASE2_JSON], conversations=conversations,
    )
    result = await interactor.ask("카페 창업을 한다면?", conversation_id=100)
    assert len(result.recommendations) == 1
    assert result.recommendations[0].name == "테스트상권"


async def test_상권_컨텍스트에_서울_평균_대비_종합점수가_주입된다(monkeypatch):
    market = _StubMarket(scores={1000001: _area_score()})
    interactor, llm, _ = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON], market=market,
    )
    await interactor.ask("역삼동 카페 어때?")
    phase2_prompt = llm.calls[2][0]
    assert "서울 평균 대비: 종합 59.6점·보통 (50점=서울 평균 수준)" in phase2_prompt
    assert "매출 성장 91.9점(상권 +21.9% vs 서울 +5.2%)" in phase2_prompt
    assert "영업 지속성 16.1점" in phase2_prompt
    assert market.score_calls == [[1000001]]


async def test_종합점수가_없는_상권은_점수_라인을_생략한다(monkeypatch):  # 무손상
    interactor, llm, _ = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON])
    await interactor.ask("역삼동 카페 어때?")
    assert "- 서울 평균 대비:" not in llm.calls[2][0]  # 규칙 문구가 아닌 컨텍스트 라인 기준


async def test_상권_컨텍스트에_상권_성격_해석이_주입된다(monkeypatch):
    # 지도 오버레이만 보던 area_narrator 인사이트를 채팅도 근거로 쓴다.
    market = _StubMarket(insights={1000001: (
        AreaInsight(key="demand_type", tone="positive", text="직장인 중심 오피스 상권입니다"),
        AreaInsight(key="avg_ticket", tone="neutral", text="건당 평균 결제액 1.2만원"),
    )})
    interactor, llm, stubs = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON], market=market,
    )
    await interactor.ask("역삼동 카페 어때?")

    context = llm.calls[2][0]
    assert "- 상권 성격: 직장인 중심 오피스 상권입니다 / 건당 평균 결제액 1.2만원" in context
    # 업종을 함께 넘겨야 해당 업종 기준 객단가가 나온다
    assert stubs["market"].insight_calls == [([1000001], "CS100010")]


async def test_상권_성격은_우선순위_상위_4개로_자른다(monkeypatch):
    # 서술자가 최대 9문장까지 만든다 — 상권 3곳이면 프롬프트가 1천 자를 넘어 7.8B가 흔들린다.
    market = _StubMarket(insights={1000001: (
        AreaInsight(key="customer_gender", tone="neutral", text="여성 우세"),
        AreaInsight(key="demand_apartment", tone="positive", text="아파트 배후 60%"),
        AreaInsight(key="spending_power", tone="neutral", text="배후 소득 상위"),
        AreaInsight(key="sales_rhythm_peak", tone="neutral", text="점심 피크"),
        AreaInsight(key="customer_age", tone="neutral", text="30대 핵심"),
        AreaInsight(key="avg_ticket", tone="neutral", text="객단가 1.2만원"),
        AreaInsight(key="demand_type", tone="positive", text="오피스형"),
    )})
    interactor, llm, _ = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON], market=market,
    )
    await interactor.ask("역삼동 카페 어때?")

    line = [ln for ln in llm.calls[2][0].splitlines() if ln.startswith("- 상권 성격:")][0]
    assert line == "- 상권 성격: 오피스형 / 객단가 1.2만원 / 30대 핵심 / 점심 피크"
    assert "여성 우세" not in line  # 정보량 낮은 축은 잘려나간다


async def test_상권_성격이_없으면_라인을_생략한다(monkeypatch):  # 열화
    interactor, llm, _ = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON])
    await interactor.ask("역삼동 카페 어때?")
    assert "- 상권 성격:" not in llm.calls[2][0]


async def test_상권_컨텍스트에_관련_지역_기사가_주입된다(monkeypatch):
    market_news = _StubMarketNews(hits=[MarketNewsHit(
        title="성수 상권 장기 정착형 리테일로 진화", area_tag="성수",
        published_at=_NOW, source="패션비즈",
    )])
    interactor, llm, _ = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON], market_news=market_news,
    )
    await interactor.ask("역삼동 카페 어때?")
    phase2_prompt = llm.calls[2][0]
    assert "[관련 지역 기사 — 의미 유사도 상위]" in phase2_prompt
    assert f"({_NOW:%Y-%m-%d} | 성수 | 패션비즈) 성수 상권 장기 정착형 리테일로 진화" in phase2_prompt
    assert market_news.calls == [("역삼동 카페 어때?", 4)]


async def test_지역_기사가_없으면_기사_블록을_생략한다(monkeypatch):  # 무손상
    interactor, llm, _ = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON])
    await interactor.ask("역삼동 카페 어때?")
    assert "[관련 지역 기사" not in llm.calls[2][0]


async def test_의도_파싱_실패면_market_폴백(monkeypatch):
    interactor, _, stubs = _build(monkeypatch, ["JSON 아님", PHASE1_JSON, PHASE2_JSON])
    result = await interactor.ask("아무 질문")
    assert stubs["market"].summary_calls == 1
    assert len(result.recommendations) == 1


async def test_stock인데_종목_추출_실패면_market_news_폴백(monkeypatch):
    news = _StubNewsSearch()
    interactor, _, _ = _build(monkeypatch, [INTENT_STOCK_NO_QUERY, "서술"], news=news)
    await interactor.ask("그 회사 어때?")
    assert len(news.calls) == 1  # 상권이 아니라 뉴스 RAG로


# --- 지표 근거 주입 ---

async def test_주식_컨텍스트에_신규_지표_해석과_참고_신호가_들어간다(monkeypatch):
    interactor, llm, _ = _build(monkeypatch, [INTENT_STOCK, "서술"])
    await interactor.ask("삼성전자 어때?")
    stock_prompt = llm.calls[1][0]  # [0]=의도 분류, [1]=7.8B 서술
    assert "%B 0.15" in stock_prompt and "ATR(14)" in stock_prompt
    assert "거래량" in stock_prompt and "12-1 모멘텀 +22.0%" in stock_prompt
    assert "과매도+볼린저 하단" in stock_prompt  # 참고 신호 라인 (True일 때만)


async def test_주식_컨텍스트에_현재가_위치가_주입된다(monkeypatch):
    # 현재가 90000은 지지 80000·저항 95000 구간의 67% 지점(중간권) — 모델이 "지지선 근처 안정"
    # 같은 근거 없는 템플릿을 못 짓게 위치 해석을 명시 주입한다.
    interactor, llm, _ = _build(monkeypatch, [INTENT_STOCK, "서술"])
    await interactor.ask("삼성전자 어때?")
    stock_prompt = llm.calls[1][0]
    assert "현재가 위치:" in stock_prompt
    assert "67% 지점" in stock_prompt and "중간권" in stock_prompt


async def test_주식_카드에_서버_결론이_실린다(monkeypatch):
    # forecast 표본이 유의(ready)하면 페이지 verdict와 같은 강한 결론 + 신호 세기 + 지켜볼 점을
    # 서버가 계산해 카드에 싣는다 — 채팅과 페이지가 어긋나지 않게.
    stocks = _StubStocks(result=_analysis(direction="UP", score=0.5))
    forecaster = _StubForecast(StockForecastSummary(
        signal_direction="UP", ready=True, up_rate=0.62, baseline_up_rate=0.55,
        sample_size=120, hits=74, ci_low=0.53, ci_high=0.70,
    ))
    interactor, _, stubs = _build(
        monkeypatch, [INTENT_STOCK, "서술"], stocks=stocks, forecaster=forecaster,
    )
    result = await interactor.ask("삼성전자 어때?")
    assert stubs["forecaster"].calls == ["005930"]  # 해석된 코드로 조회
    assert "+7%p 높았습니다" in result.stock.headline  # edge = 62-55
    assert result.stock.strength == "보통"  # |0.5| vs 임계 0.3·0.6
    assert "지켜보세요" in result.stock.watch


async def test_주식_카드_결론은_forecast_없으면_약한_결론으로_열화(monkeypatch):
    # 표본 없음(forecast None)이면 방향은 있어도 "근거는 약합니다"로 — 없는 확신 금지.
    stocks = _StubStocks(result=_analysis(direction="UP", score=0.5))
    interactor, _, _ = _build(
        monkeypatch, [INTENT_STOCK, "서술"], stocks=stocks,
        forecaster=_StubForecast(None),
    )
    result = await interactor.ask("삼성전자 어때?")
    assert "근거는 약합니다" in result.stock.headline


async def test_주식_카드에_펀더멘털_가치_한줄이_실린다(monkeypatch):
    # "이 회사 싼가/튼튼한가" — fundamental_narrator 해석 대표 2개를 카드 value에 싣는다(3개면 앞 2개).
    fundamentals = _StubFundamentals([
        FundamentalInsightItem(key="per", tone="positive", text="PER 6.6배 — 저평가권"),
        FundamentalInsightItem(key="roe", tone="positive", text="ROE 18% — 체력 양호"),
        FundamentalInsightItem(key="pbr", tone="neutral", text="PBR 1.2배"),
    ])
    interactor, _, stubs = _build(
        monkeypatch, [INTENT_STOCK, "서술"], fundamentals=fundamentals,
    )
    result = await interactor.ask("삼성전자 어때?")
    assert stubs["fundamentals"].calls == ["005930"]
    assert result.stock.value == ["PER 6.6배 — 저평가권", "ROE 18% — 체력 양호"]


async def test_펀더멘털_미수집이면_가치줄_없음(monkeypatch):  # 열화
    interactor, _, _ = _build(
        monkeypatch, [INTENT_STOCK, "서술"], fundamentals=_StubFundamentals([]),
    )
    result = await interactor.ask("삼성전자 어때?")
    assert result.stock.value == []


async def test_서술_컨텍스트에_과거통계와_펀더멘털이_들어간다(monkeypatch):
    # 예전엔 답변을 만든 뒤에 조회해 카드에만 실렸고, 본문은 밸류에이션·통계를 못 말했다.
    forecaster = _StubForecast(StockForecastSummary(
        signal_direction="UP", ready=True, up_rate=0.62, baseline_up_rate=0.55,
        sample_size=120, hits=74, ci_low=0.53, ci_high=0.70,
    ))
    fundamentals = _StubFundamentals([
        FundamentalInsightItem(key="per", tone="positive", text="PER 6.6배 — 저평가권"),
    ])
    interactor, llm, _ = _build(
        monkeypatch, [INTENT_STOCK, "서술"], forecaster=forecaster, fundamentals=fundamentals,
    )
    await interactor.ask("삼성전자 어때?")

    context = llm.calls[1][0]  # 0=의도분류, 1=종목 서술
    assert "과거 120건 중 62%가 상승" in context
    assert "평소 55%" in context and "95% 구간 53%~70%" in context  # 표본·기준선·CI 병기 필수
    assert "미래 확률이 아니며" in context  # 확률 단정 금지 가드
    assert "PER 6.6배 — 저평가권" in context


async def test_표본이_유의하지_않으면_수치를_주지_않는다(monkeypatch):
    # ready=False면 7.8B가 확률로 단정하지 못하도록 숫자 자체를 뺀다.
    forecaster = _StubForecast(StockForecastSummary(
        signal_direction="UP", ready=False, up_rate=0.71, baseline_up_rate=0.55,
        sample_size=7, hits=5,
    ))
    interactor, llm, _ = _build(monkeypatch, [INTENT_STOCK, "서술"], forecaster=forecaster)
    await interactor.ask("삼성전자 어때?")

    context = llm.calls[1][0]
    assert "7건뿐이라 통계적으로 유의하지 않음" in context
    assert "71%" not in context


async def test_forecast_펀더멘털_없으면_해당_블록_생략(monkeypatch):  # 열화
    interactor, llm, _ = _build(
        monkeypatch, [INTENT_STOCK, "서술"],
        forecaster=_StubForecast(None), fundamentals=_StubFundamentals([]),
    )
    await interactor.ask("삼성전자 어때?")

    context = llm.calls[1][0]
    assert "과거 통계" not in context and "가치·체력" not in context


def test_verdict_파리티_고정():  # www/lib/verdict.ts와 같은 문안이어야 채팅==페이지
    strong = StockForecastSummary(
        signal_direction="UP", ready=True, up_rate=0.62, baseline_up_rate=0.55,
        sample_size=120, hits=74, ci_low=0.53, ci_high=0.70,
    )
    head, _ = verdict("UP", strong)
    assert head == "상승 쪽 신호이고, 과거 통계도 평소보다 +7%p 높았습니다"
    assert verdict("NEUTRAL", None)[0] == "지금은 방향을 말하기 어렵습니다"
    assert verdict("UP", None)[0] == "상승 쪽 신호가 있지만, 근거는 약합니다"
    assert strength(0.2, 0.3) == "약" and strength(0.5, 0.3) == "보통" and strength(0.7, 0.3) == "강"


async def test_참고_신호_false면_문구_자체가_없다(monkeypatch):  # 소형 모델 오독 차단
    stocks = _StubStocks(result=_analysis(reference_up_signal=False))
    interactor, llm, _ = _build(monkeypatch, [INTENT_STOCK, "서술"], stocks=stocks)
    await interactor.ask("삼성전자 어때?")
    # 규칙 문구(STOCK_ANSWER_PROMPT)가 아니라 컨텍스트의 신호 라인이 없어야 한다
    assert "과매도+볼린저 하단" not in llm.calls[1][0]


async def test_stock_카드에_신규_6필드가_매핑된다(monkeypatch):
    interactor, _, _ = _build(monkeypatch, [INTENT_STOCK, "서술"])
    result = await interactor.ask("삼성전자 어때?")
    card = result.stock
    assert card.atrPct == 0.025 and card.bbPercentB == 0.15
    assert card.volumeRatio == 1.8 and card.obvSlope == 0.5
    assert card.momentum12To1 == 0.22 and card.referenceUpSignal is True


# --- 뉴스 RAG ---

async def test_주식_답변에_관련_뉴스_섹션이_라벨과_함께_붙는다(monkeypatch):
    news = _StubNewsSearch(hits=[_hit(title="새 소식")])
    interactor, llm, _ = _build(monkeypatch, [INTENT_STOCK, "서술"], news=news)
    await interactor.ask("삼성전자 어때?")
    assert news.calls[0][1] == "005930"  # 해석된 심볼로 범위 제한
    stock_prompt = llm.calls[1][0]
    assert "관련 뉴스(감성 라벨)" in stock_prompt and "호재" in stock_prompt


async def test_뉴스_히트가_없으면_관련_뉴스_섹션이_생략된다(monkeypatch):  # 무손상
    interactor, llm, _ = _build(monkeypatch, [INTENT_STOCK, "서술"])
    await interactor.ask("삼성전자 어때?")
    assert "관련 뉴스(감성 라벨)" not in llm.calls[1][0]


async def test_market_news_히트가_없으면_데이터_부재를_안내한다(monkeypatch):
    interactor, llm, _ = _build(monkeypatch, [INTENT_MARKET_NEWS, "열화 서술"])
    await interactor.ask("업황 어때?")
    assert "수집된 관련 뉴스가 없습니다" in llm.calls[1][0]


async def test_종목_해석_실패면_안내문을_저장하고_반환한다(monkeypatch):
    stocks = _StubStocks(fail=True)
    interactor, _, stubs = _build(monkeypatch, [INTENT_STOCK], stocks=stocks)
    result = await interactor.ask("이상한종목 어때?")
    assert "다시 물어봐" in result.text
    assert stubs["conversations"].saved[-1][0] == "assistant"


# --- phase1 상권 컨텍스트: 질문 지역 우선 ---

def _summary_two_areas() -> AreaSummary:
    seongsu = AreaInfo(trdar_code=1, trdar_name="성수역", district_name="성동구",
                       adm_dong_name="성수1가1동", lat=37.5, lng=127.0)
    noryang = AreaInfo(trdar_code=2, trdar_name="노량진역(노량진)", district_name="동작구",
                       adm_dong_name="노량진1동", lat=37.5, lng=126.9)
    # 매출은 노량진이 압도적 — 언급 매칭 없으면 노량진이 첫 행이어야 한다
    return AreaSummary(areas=[seongsu, noryang], latest_quarter=20254,
                       sales_by_code={1: 10_000_000, 2: 999_000_000})


async def test_행정동_언급_상권이_매출과_무관하게_컨텍스트_최상단_별표(monkeypatch):
    interactor, _, _ = _build(monkeypatch, [])
    context = interactor._build_area_context(_summary_two_areas(), "성수동에 카페 차릴만해?")
    rows = context.splitlines()[1:]
    assert rows[0].startswith("1|성수역") and rows[0].endswith("★")  # 성수1가1동 → 어간 '성수' 매칭
    assert rows[1].startswith("2|") and rows[1].endswith("|")  # 노량진은 표시 없음


async def test_지역_언급_없으면_매출순_유지(monkeypatch):
    interactor, _, _ = _build(monkeypatch, [])
    context = interactor._build_area_context(_summary_two_areas(), "카페 차릴만한 곳 추천해줘")
    rows = context.splitlines()[1:]
    assert rows[0].startswith("2|")  # 매출 상위 노량진 먼저
    assert not any(r.endswith("★") for r in rows)


async def test_자치구_언급도_계속_매칭된다(monkeypatch):  # 기존 동작 보존
    interactor, _, _ = _build(monkeypatch, [])
    context = interactor._build_area_context(_summary_two_areas(), "성동구 쪽 어때?")
    assert context.splitlines()[1].startswith("1|성수역")


async def test_지역_언급_시_LLM이_다른_상권을_골라도_언급_지역으로_보정된다(monkeypatch):
    # phase1(2.4B 스텁)이 노량진(code 2)을 고르지만, 질문은 성수동 — 가드가 성수(code 1)로 교체
    phase1_wrong = '{"service_code": "CS100010", "service_name": "커피-음료", "trdar_codes": [2]}'
    phase2 = '{"text": "요약", "areas": [{"trdar_code": 1, "reason": "이유"}]}'
    interactor, _, stubs = _build(monkeypatch, [INTENT_MARKET, phase1_wrong, phase2])
    stubs["market"].summary = _summary_two_areas()

    async def _fixed_summary():
        return _summary_two_areas()
    stubs["market"].get_area_summary = _fixed_summary

    result = await interactor.ask("성수동에 카페 차릴만해?")
    assert [a.id for a in result.recommendations] == ["1"]  # 성수역만


# --- 서울 외 지역 가드 ---

async def test_서울_외_지역_질문은_LLM_호출_없이_준비중_안내(monkeypatch):
    interactor, llm, stubs = _build(monkeypatch, [INTENT_MARKET])
    result = await interactor.ask("수원역 상권 분석해줘")
    assert "서울" in result.text and "준비 중" in result.text and "수원" in result.text
    assert result.recommendations == []
    assert len(llm.calls) == 1  # phase0(의도 분류)만 — phase1/phase2 미호출
    assert stubs["conversations"].saved[-1] == ("assistant", result.text)


async def test_서울_지명이_함께_언급되면_기존_흐름_유지(monkeypatch):
    # 기본 스텁 상권이 강남구 — "강남" 언급이 있으면 서울 분석으로 진행한다
    interactor, _, _ = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON])
    result = await interactor.ask("강남이랑 수원 중에 카페는 어디가 나아?")
    assert len(result.recommendations) == 1


# --- 멀티턴 시나리오 (E2E 시나리오 3종 — 인터랙터 레벨) ---

async def test_시나리오_주식_업황_상권_연속_질문(monkeypatch):
    conversations = _StubConversations(history=[
        Message(id=1, conversation_id=200, role="user", content="삼성전자 어때?", created_at=_NOW),
        Message(id=2, conversation_id=200, role="assistant", content="주식 서술", created_at=_NOW),
    ])
    news = _StubNewsSearch(hits=[_hit()])
    interactor, llm, stubs = _build(
        monkeypatch,
        [INTENT_MARKET_NEWS, "업황 서술", INTENT_MARKET, PHASE1_JSON, PHASE2_JSON],
        news=news, conversations=conversations,
    )
    r1 = await interactor.ask("그럼 업황은 어때?", conversation_id=200)
    assert "이전 대화" in llm.calls[0][0] and "삼성전자 어때?" in llm.calls[0][0]  # history 전달
    r2 = await interactor.ask("성수동 상권도 알려줘", conversation_id=200)
    assert r1.conversationId == r2.conversationId == 200
    roles = [role for role, _ in stubs["conversations"].saved]
    assert roles == ["user", "assistant", "user", "assistant"]


# --- 대화 히스토리 (payload 저장 + 목록/복원) ---

async def test_새_대화는_user_id를_소유자로_기록한다(monkeypatch):
    interactor, _, stubs = _build(monkeypatch, [INTENT_STOCK, "서술"])
    await interactor.ask("삼성전자 어때?", user_id=7)
    assert stubs["conversations"].created_user_ids == [7]


async def test_주식_답변은_stock_카드를_payload로_저장한다(monkeypatch):
    interactor, _, stubs = _build(monkeypatch, [INTENT_STOCK, "서술"])
    await interactor.ask("삼성전자 어때?")
    assistant_payload = stubs["conversations"].payloads[-1]
    assert assistant_payload is not None
    assert assistant_payload["stock"]["symbol"] == "005930"


async def test_상권_답변은_recommendations를_payload로_저장한다(monkeypatch):
    interactor, _, stubs = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON])
    await interactor.ask("성수동 카페 어때?")
    assistant_payload = stubs["conversations"].payloads[-1]
    assert assistant_payload is not None
    assert assistant_payload["recommendations"][0]["name"] == "테스트상권"


async def test_텍스트만인_답변은_payload가_없다(monkeypatch):
    interactor, _, stubs = _build(monkeypatch, [INTENT_MARKET_NEWS, "업황 서술"])
    await interactor.ask("업황 어때?")
    assert stubs["conversations"].payloads[-1] is None


async def test_market_news_답변은_뉴스_카드를_응답과_payload에_동반한다(monkeypatch):
    news = _StubNewsSearch(hits=[_hit()])
    interactor, _, stubs = _build(
        monkeypatch, [INTENT_MARKET_NEWS, "업황 서술"], news=news,
    )
    result = await interactor.ask("반도체 업황 어때?")

    assert len(result.news) == 1
    card = result.news[0]
    assert card.title == "반도체 업황 회복 조짐"
    assert card.ticker == "005930.KS"
    assert card.publishedAt == f"{_NOW:%Y-%m-%d}"
    assert card.sentiment == 0.7 and card.eventType == "실적"

    assistant_payload = stubs["conversations"].payloads[-1]
    assert assistant_payload is not None
    assert assistant_payload["news"][0]["title"] == "반도체 업황 회복 조짐"


async def test_market_news_히트가_없으면_뉴스_카드도_비어있다(monkeypatch):
    interactor, _, stubs = _build(monkeypatch, [INTENT_MARKET_NEWS, "부재 안내"])
    result = await interactor.ask("업황 어때?")
    assert result.news == []
    assert stubs["conversations"].payloads[-1] is None


async def test_남의_대화_메시지는_미존재와_같은_예외를_낸다(monkeypatch):
    conversations = _StubConversations(
        conversation=Conversation(id=200, created_at=_NOW, user_id=1),
    )
    interactor, _, _ = _build(monkeypatch, [], conversations=conversations)
    with pytest.raises(ConversationNotFoundError):
        await interactor.conversation_messages(200, user_id=2)


async def test_소유자는_메시지를_payload_포함으로_받는다(monkeypatch):
    history = [Message(id=1, conversation_id=200, role="assistant", content="답",
                       created_at=_NOW, payload={"stock": {"symbol": "005930"}})]
    conversations = _StubConversations(
        history=history,
        conversation=Conversation(id=200, created_at=_NOW, user_id=1),
    )
    interactor, _, _ = _build(monkeypatch, [], conversations=conversations)
    messages = await interactor.conversation_messages(200, user_id=1)
    assert messages[0].payload == {"stock": {"symbol": "005930"}}


async def test_구버전_익명_대화는_인증_사용자에게_허용된다(monkeypatch):
    conversations = _StubConversations(
        conversation=Conversation(id=200, created_at=_NOW, user_id=None),
    )
    interactor, _, _ = _build(monkeypatch, [], conversations=conversations)
    assert await interactor.conversation_messages(200, user_id=1) == []


# --- phase0 general(제미나이) 분기 ---

async def test_general_의도면_허브_Gemini_포트로_답한다(monkeypatch):
    interactor, _, stubs = _build(monkeypatch, [INTENT_GENERAL])
    result = await interactor.ask("카파시가 누구야?")
    assert stubs["gemini"].prompts == ["카파시가 누구야?"]
    assert result.text == "제미나이 답변"
    assert result.recommendations == []


async def test_general_분기에서_Gemini_실패면_안내로_열화한다(monkeypatch):
    interactor, _, _ = _build(monkeypatch, [INTENT_GENERAL], gemini=_StubGemini(fail=True))
    result = await interactor.ask("카파시가 누구야?")
    assert "일시적인 문제" in result.text


# --- 통화 단위 (미국 종목을 '원'으로 서술하던 오답 고정) ---

@pytest.mark.parametrize(
    "symbol, expected",
    [("005930", "원"), ("005930.KS", "원"), ("000660.KQ", "원"),
     ("TSLA", "달러"), ("BRK-B", "달러"), ("SNDK", "달러")],
)
def test_티커로_통화를_정한다(symbol, expected):
    assert ChatInteractor._currency_unit(symbol) == expected


def test_주식_컨텍스트의_가격에는_통화가_붙는다():
    """단위를 안 주면 모델이 추측해 미국 종목을 '원'으로 서술했다(실측 회귀)."""
    context = ChatInteractor._format_stock_context("샌디스크 어때?", _analysis(symbol="SNDK"))
    assert "90,000.00달러" in context  # 현재가
    assert "88,000.00달러" in context and "85,000.00달러" in context  # 이동평균
    assert "80,000.00달러" in context and "95,000.00달러" in context  # 지지·저항
    assert "원" not in context.split("[SNDK 분석 데이터]")[1].split("- 방향 신호")[0]

    kr = ChatInteractor._format_stock_context("삼성전자 어때?", _analysis(symbol="005930"))
    assert "90,000.00원" in kr


# ── 유동인구 피크시간 구간 폭 보정 ──
# 구간 폭이 제각각이라(0~6시 6시간, 11~14시 3시간) 총합 최대를 그대로 쓰면 가장 넓은
# 새벽 구간이 늘 피크로 뽑힌다. LLM 컨텍스트에 그대로 실려 답변까지 틀어진다.

class _FloatingRaw:
    """미아사거리 2026 4분기 실측값."""
    time_00_06_floating_pop = 81994
    time_06_11_floating_pop = 70659
    time_11_14_floating_pop = 46638
    time_14_17_floating_pop = 49070
    time_17_21_floating_pop = 62682
    time_21_24_floating_pop = 42716


def test_피크시간은_시간당_평균으로_고른다():
    from chat.app.use_cases.chat_interactor import TIME_FIELDS, _top_time_field

    # 총합 1위는 새벽 0~6시(81,994)지만 시간당으로는 최하위(13,665/h)다
    assert _top_time_field(_FloatingRaw(), TIME_FIELDS) == "오후 2~5시"


def test_총합_최대는_넓은_구간에_쏠린다():
    """보정이 없으면 어떤 값이 나오는지 고정 — 회귀 시 이 대비가 깨진다."""
    from chat.app.use_cases.chat_interactor import TIME_FIELDS, _top_field

    naive = _top_field(_FloatingRaw(), [(f, label) for f, label, _ in TIME_FIELDS])
    assert naive == "새벽 0~6시"


async def test_점포_컨텍스트에_절대건수와_경쟁강도가_붙는다(monkeypatch):
    # 율(%)만 주면 소규모 상권에서 오독한다 — "3개 중 1개 폐업 = 33%".
    market = _StubMarket(raw=_raw_stat(
        has_store=True, store_count=12, closure_rate=8.3, opening_rate=4.1,
        franchise_store_count=3, closure_store_count=1, opening_store_count=2,
        similar_industry_store_count=7,
    ))
    interactor, llm, _ = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON], market=market,
    )
    await interactor.ask("역삼동 카페 어때?")

    context = llm.calls[2][0]
    assert "분기 폐업률 8.3%(1개)" in context
    assert "분기 개업률 4.1%(2개)" in context
    assert "동일 업종 7개 경쟁" in context


async def test_폐업까지_걸린_개월이_영업개월과_함께_나온다(monkeypatch):
    # 생존 중 점포의 영업개월만으론 "얼마 만에 닫는가"를 알 수 없다.
    market = _StubMarket(raw=_raw_stat(
        has_cc=True, change_indicator_name="상권확장", operating_months_avg=48,
        region_operating_months_avg=40, closure_months_avg=22, region_closure_months_avg=25,
    ))
    interactor, llm, _ = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON], market=market,
    )
    await interactor.ask("역삼동 카페 어때?")

    context = llm.calls[2][0]
    assert "폐업 점포는 평균 22개월 만에 닫음 (지역 평균 25개월)" in context


async def test_절대건수가_없으면_율만_쓴다(monkeypatch):  # 열화
    market = _StubMarket(raw=_raw_stat(
        has_store=True, store_count=12, closure_rate=8.3, opening_rate=4.1,
        franchise_store_count=3,
    ))
    interactor, llm, _ = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON], market=market,
    )
    await interactor.ask("역삼동 카페 어때?")

    context = llm.calls[2][0]
    assert "분기 폐업률 8.3% " in context and "8.3%(" not in context
