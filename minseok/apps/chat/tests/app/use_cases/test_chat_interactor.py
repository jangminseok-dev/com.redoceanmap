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
    AreaRankingInfo,
    AreaRawStat,
    AreaScoreComponent,
    AreaScoreInfo,
    AreaTrendPoint,
    AreaSummary,
    PermitChurnInfo,
    ServiceCode,
)
from chat.domain.services.verdict import strength, verdict
from hub.app.dtos.fundamental_dto import FundamentalInsightItem
from hub.app.dtos.market_news_dto import MarketNewsHit
from hub.app.dtos.news_dto import NewsHit, NewsKeyword
from hub.app.dtos.stock_analysis_dto import StockAnalysisResult
from hub.app.dtos.stock_forecast_dto import StockForecastSummary
from hub.app.dtos.user_profile_dto import UserProfileSummary
from hub.app.dtos.forecast_refit_dto import (
    RefitCandidateRow,
    RefitHorizonBoard,
    RefitReportInfo,
)
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
    def __init__(self, hits: list[NewsHit] | None = None, keywords=None):
        self.hits = hits or []
        self.keywords = keywords or []
        self.calls: list[tuple[str, str | None, int]] = []
        self.keyword_calls: list[str] = []

    async def search(self, query: str, ticker: str | None = None, limit: int = 5) -> list[NewsHit]:
        self.calls.append((query, ticker, limit))
        return self.hits

    async def top_keywords(self, ticker: str, limit: int = 5):
        self.keyword_calls.append(ticker)
        return self.keywords


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
                 raw: AreaRawStat | None = None,
                 permit_churn: dict[int, PermitChurnInfo] | None = None,
                 areas: list[AreaInfo] | None = None,
                 yoy: dict[int, float | None] | None = None,
                 ranking: list[AreaRankingInfo] | None = None,
                 services: list[ServiceCode] | None = None):
        self.summary_calls = 0
        self.scores = scores or {}
        self.score_calls: list[list[int]] = []
        self.insights = insights or {}
        self.insight_calls: list[tuple[list[int], str | None]] = []
        self.raw = raw
        self.permit_churn = permit_churn or {}
        self.permit_calls: list[list[int]] = []
        self._areas = areas  # None이면 기존 단일 상권(무손상)
        self._yoy = yoy or {}
        self.ranking = ranking or []
        self.ranking_calls: list[str | None] = []
        self.services = services or [ServiceCode(code="CS100010", name="커피-음료")]

    async def get_area_summary(self) -> AreaSummary:
        self.summary_calls += 1
        areas = self._areas or [
            AreaInfo(trdar_code=1000001, trdar_name="테스트상권", district_name="강남구",
                     adm_dong_name="역삼동", lat=37.5, lng=127.0)
        ]
        return AreaSummary(
            areas=areas, latest_quarter=20254,
            sales_by_code={a.trdar_code: 100_000_000 for a in areas},
            yoy_by_code=self._yoy,
        )

    async def get_service_codes(self) -> list[ServiceCode]:
        return self.services

    async def get_area_raw_stats(self, codes, service_code, quarter):
        return {c: (self.raw or _raw_stat()) for c in codes}

    async def get_area_scores(self, trdar_codes):
        self.score_calls.append(list(trdar_codes))
        return self.scores

    async def get_area_ranking(self, service_code=None):
        self.ranking_calls.append(service_code)
        return self.ranking

    async def get_area_insights(self, trdar_codes, service_code=None):
        self.insight_calls.append((list(trdar_codes), service_code))
        return self.insights

    async def get_area_permit_churn(self, trdar_codes, months=12):
        self.permit_calls.append(list(trdar_codes))
        return self.permit_churn


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


class _StubProfiles:
    def __init__(self, summary: UserProfileSummary | None = None, fail: bool = False):
        self.summary = summary
        self.fail = fail
        self.calls: list[int] = []

    async def get_profile(self, user_id: int) -> UserProfileSummary | None:
        self.calls.append(user_id)
        if self.fail:
            raise RuntimeError("프로파일 저장소 불가")
        return self.summary


def _profile() -> UserProfileSummary:
    return UserProfileSummary(
        purpose="startup", purpose_label="창업 준비", risk_label="안정추구형",
        budget_label="5천만~1억원", debt_label="부채 없음", horizon_label="중기(1~3년)",
    )


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
           market=None, market_news=None, gemini=None, forecaster=None, fundamentals=None,
           profiles=None):
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
        forecaster=forecaster, fundamentals=fundamentals, profiles=profiles,
    )
    return interactor, llm, dict(market=market, recorder=recorder,
                                 conversations=conversations, stocks=stocks, news=news,
                                 market_news=market_news, gemini=gemini, forecaster=forecaster,
                                 fundamentals=fundamentals, profiles=profiles)


# --- phase0 3분류 라우팅 ---

async def test_stock_의도면_분석_포트를_호출하고_카드를_반환한다(monkeypatch):
    interactor, _, stubs = _build(monkeypatch, [INTENT_STOCK, "주식 서술"])
    result = await interactor.ask("삼성전자 어때?")
    assert stubs["stocks"].queries == ["삼성전자"]
    assert result.stock is not None and result.stock.symbol == "005930"
    # 답변 뒤에 책임 고지가 코드로 붙는다(answer_guard) — 모델이 빠뜨려도 절대 규칙을 지킨다
    assert result.text.startswith("주식 서술")
    assert result.text.endswith("투자 판단과 그 결과는 본인 책임입니다.")


async def test_비교_질문_리스트_반환은_첫_종목만_분석하고_고지한다(monkeypatch):
    # 7.8B가 스키마(단일 문자열) 대신 리스트를 반환한 실사례(2026-08-31 프로덕션)
    intent = '{"intent": "stock", "stock_query": ["테슬라", "애플"]}'
    interactor, _, stubs = _build(monkeypatch, [intent, "주식 서술"])
    result = await interactor.ask("테슬라랑 애플 중 어디에 투자할까?")
    assert stubs["stocks"].queries == ["테슬라"]  # 리스트 표기가 리졸버로 흘러가지 않는다
    assert result.text.startswith("여러 종목 비교는 아직 지원하지 않아 '테슬라'만 분석했어요.")
    assert "애플" in result.text.split("\n\n")[0]
    assert result.text.endswith("투자 판단과 그 결과는 본인 책임입니다.")  # 고지 유지


async def test_비교_질문_쉼표_결합_문자열도_첫_종목만_분석한다(monkeypatch):
    # 세 번째 변형(2026-09-01 배포 검증 실측): "테슬라, 애플" 단일 문자열
    intent = '{"intent": "stock", "stock_query": "테슬라, 애플"}'
    interactor, _, stubs = _build(monkeypatch, [intent, "주식 서술"])
    result = await interactor.ask("테슬라랑 애플 중 어디에 투자할까?")
    assert stubs["stocks"].queries == ["테슬라"]
    assert result.text.startswith("여러 종목 비교는 아직 지원하지 않아 '테슬라'만 분석했어요.")


async def test_비교_질문_리스트_문자열_표기도_첫_종목만_분석한다(monkeypatch):
    # 리스트를 문자열로 흉내낸 변형("['테슬라', '애플']") — str() 캐스팅 시절의 실패 모양
    intent = '{"intent": "stock", "stock_query": "[\'테슬라\', \'애플\']"}'
    interactor, _, stubs = _build(monkeypatch, [intent, "주식 서술"])
    await interactor.ask("테슬라랑 애플 비교해줘")
    assert stubs["stocks"].queries == ["테슬라"]


async def test_단일_종목_질문은_고지_없이_기존과_동일하다(monkeypatch):  # 무손상 회귀
    interactor, _, stubs = _build(monkeypatch, [INTENT_STOCK, "주식 서술"])
    result = await interactor.ask("삼성전자 어때?")
    assert stubs["stocks"].queries == ["삼성전자"]
    assert "비교는 아직 지원하지 않아" not in result.text


async def test_market_news_의도면_뉴스_검색을_코퍼스_횡단으로_호출한다(monkeypatch):
    news = _StubNewsSearch(hits=[_hit()])
    interactor, _, _ = _build(monkeypatch, [INTENT_MARKET_NEWS, "업황 서술"], news=news)
    result = await interactor.ask("반도체 업황 어때?")
    assert news.calls == [("반도체 업황 어때?", None, 8)]
    assert result.text.startswith("업황 서술") and result.recommendations == []
    assert result.text.endswith("투자 판단과 그 결과는 본인 책임입니다.")


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


async def test_진행_콜백이_market_단계를_순서대로_알린다(monkeypatch):
    stages: list[str] = []
    interactor, _, _ = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON])
    await interactor.ask("역삼동 카페 어때?", on_stage=lambda s, label: stages.append(s))
    assert stages == ["intent", "select", "data", "narrate"]


async def test_진행_콜백이_stock_단계를_순서대로_알린다(monkeypatch):
    stages: list[str] = []
    interactor, _, _ = _build(monkeypatch, [INTENT_STOCK, "주식 서술"])
    await interactor.ask("삼성전자 어때?", on_stage=lambda s, label: stages.append(s))
    assert stages == ["intent", "analyze", "narrate"]


async def test_진행_콜백_실패는_답변을_깨지_않는다(monkeypatch):
    def boom(stage, label):
        raise RuntimeError("통지 실패")
    interactor, _, _ = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON])
    result = await interactor.ask("역삼동 카페 어때?", on_stage=boom)
    assert len(result.recommendations) == 1  # 통지는 부가 기능 — 실패해도 답변은 나간다


async def test_파싱_실패는_1회_재시도로_복구된다(monkeypatch):
    # phase1 첫 응답이 깨져도 재호출이 성공하면 사용자는 오류를 보지 않는다(실측 1/120 흡수)
    interactor, llm, _ = _build(
        monkeypatch, [INTENT_MARKET, "JSON 아님", PHASE1_JSON, PHASE2_JSON]
    )
    result = await interactor.ask("성수동 카페 어때?")
    assert len(result.recommendations) == 1
    assert len(llm.calls) == 4  # phase0 + phase1×2(재시도) + phase2


async def test_리스크_문장이_없으면_데이터_기반_유의점을_붙인다(monkeypatch):
    interactor, _, _ = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON])
    result = await interactor.ask("역삼동 카페 어때?")
    reason = result.recommendations[0].reason
    assert reason.startswith("추천 이유")
    assert "유의할 점:" in reason  # 스텁 통계는 폐업·경쟁이 없어 데이터 한계 문구가 붙는다


async def test_phase2가_코드를_문자열로_돌려줘도_이유가_매핑된다(monkeypatch):
    # 3차 실측: 모델이 "trdar_code": "1000001"(문자열)로 반환 → int 조회 전부 미스 →
    # 추천 카드의 69%가 이유 없이 나갔다. 정규화로 매핑을 복구한다.
    phase2_str_code = ('{"text": "요약", "areas": [{"trdar_code": "1000001",'
                       ' "reason": "좋아요. 유의할 점: 경쟁 확인."}]}')
    interactor, _, _ = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, phase2_str_code])
    result = await interactor.ask("역삼동 카페 어때?")
    assert result.recommendations[0].reason.startswith("좋아요")


async def test_리스크_문장이_이미_있으면_덧붙이지_않는다(monkeypatch):
    phase2_with_risk = ('{"text": "요약", "areas": [{"trdar_code": 1000001,'
                        ' "reason": "좋아요. 유의할 점: 폐업률 확인."}]}')
    interactor, _, _ = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, phase2_with_risk])
    result = await interactor.ask("역삼동 카페 어때?")
    assert result.recommendations[0].reason.count("유의할 점") == 1


async def test_역이_붙은_상권명은_역을_뗀_지명으로도_매칭된다(monkeypatch):
    # 실측: "건대입구역 6번" 상권이 "건대입구 쪽" 질문과 안 맞아 지역 가드가 침묵했다
    areas = [
        AreaInfo(trdar_code=1000001, trdar_name="건대입구역 6번", district_name="광진구",
                 adm_dong_name="화양동", lat=37.5, lng=127.0),
        AreaInfo(trdar_code=1000002, trdar_name="테스트상권", district_name="강남구",
                 adm_dong_name="역삼동", lat=37.5, lng=127.0),
    ]
    phase1_wrong = ('{"service_code": "CS100010", "service_name": "커피-음료",'
                    ' "trdar_codes": [1000002]}')
    interactor, _, _ = _build(
        monkeypatch, [INTENT_MARKET, phase1_wrong, PHASE2_JSON],
        market=_StubMarket(areas=areas),
    )
    result = await interactor.ask("건대입구 쪽 술집 상권 알려줘")
    assert [r.id for r in result.recommendations] == ["1000001"]  # 지역 가드가 보정


async def test_지시어_후속질문은_직전_추천으로_후보를_제한한다(monkeypatch):
    # 첫 baseline 실측: "그 중에서"라고 물어도 모델이 10건 전부 이웃 상권을 섞었다(집중률 0%).
    # 지시어 + 직전 추천 존재면 phase1이 무엇을 골랐든 직전 추천으로 자른다.
    areas = [
        AreaInfo(trdar_code=1000001, trdar_name="테스트상권", district_name="강남구",
                 adm_dong_name="역삼동", lat=37.5, lng=127.0),
        AreaInfo(trdar_code=1000002, trdar_name="이웃상권", district_name="서초구",
                 adm_dong_name="서초동", lat=37.4, lng=127.0),
    ]
    conversations = _StubConversations(history=[
        Message(id=1, conversation_id=100, role="user", content="강남 상권 어때?",
                created_at=_NOW, payload=None),
        Message(id=2, conversation_id=100, role="assistant", content="상권 추천",
                created_at=_NOW,
                payload={"recommendations": [{"id": "1000001", "name": "테스트상권"}]}),
    ])
    phase1_both = ('{"service_code": "CS100010", "service_name": "커피-음료",'
                   ' "trdar_codes": [1000001, 1000002]}')
    interactor, _, _ = _build(
        monkeypatch, [INTENT_MARKET, phase1_both, PHASE2_JSON],
        conversations=conversations, market=_StubMarket(areas=areas),
    )
    result = await interactor.ask("그 중에서 제일 나은 곳은?", conversation_id=100)
    assert [r.id for r in result.recommendations] == ["1000001"]  # 이웃상권이 잘려나간다


async def test_제외어가_있으면_직전_추천으로_제한하지_않는다(monkeypatch):
    # P2 확대 이후에도 "말고/빼고" 류는 제한하지 않는다 — 직전 추천으로 자르면 정반대 답
    areas = [
        AreaInfo(trdar_code=1000001, trdar_name="테스트상권", district_name="강남구",
                 adm_dong_name="역삼동", lat=37.5, lng=127.0),
        AreaInfo(trdar_code=1000002, trdar_name="이웃상권", district_name="서초구",
                 adm_dong_name="서초동", lat=37.4, lng=127.0),
    ]
    conversations = _StubConversations(history=[
        Message(id=1, conversation_id=100, role="user", content="강남 상권 어때?",
                created_at=_NOW, payload=None),
        Message(id=2, conversation_id=100, role="assistant", content="상권 추천",
                created_at=_NOW,
                payload={"recommendations": [{"id": "1000001", "name": "테스트상권"}]}),
    ])
    phase1_both = ('{"service_code": "CS100010", "service_name": "커피-음료",'
                   ' "trdar_codes": [1000001, 1000002]}')
    phase2_both = ('{"text": "요약", "areas": ['
                   '{"trdar_code": 1000001, "reason": "이유1"},'
                   '{"trdar_code": 1000002, "reason": "이유2"}]}')
    interactor, _, _ = _build(
        monkeypatch, [INTENT_MARKET, phase1_both, phase2_both],
        conversations=conversations, market=_StubMarket(areas=areas),
    )
    result = await interactor.ask("숙대 말고 다른 후보도 보여줘", conversation_id=100)
    assert [r.id for r in result.recommendations] == ["1000001", "1000002"]


async def test_비지시어_후속도_직전_추천으로_제한한다(monkeypatch):
    # 3차 실측 P2: "경쟁 가게는 몇 개나 돼?" 류에서 phase1이 전면 재선택해
    # 동대문·홍대로 리셋됐다 — 새 지역 미언급이면 지시어 없이도 직전 추천으로 제한한다.
    areas = [
        AreaInfo(trdar_code=1000001, trdar_name="테스트상권", district_name="강남구",
                 adm_dong_name="역삼동", lat=37.5, lng=127.0),
        AreaInfo(trdar_code=1000002, trdar_name="이웃상권", district_name="서초구",
                 adm_dong_name="서초동", lat=37.4, lng=127.0),
    ]
    conversations = _StubConversations(history=[
        Message(id=1, conversation_id=100, role="user", content="강남 상권 어때?",
                created_at=_NOW, payload=None),
        Message(id=2, conversation_id=100, role="assistant", content="상권 추천",
                created_at=_NOW,
                payload={"recommendations": [
                    {"id": "1000001", "name": "테스트상권",
                     "serviceCode": "CS100001", "category": "치킨전문점"}]}),
    ])
    phase1_other = ('{"service_code": "CS100010", "service_name": "커피-음료",'
                    ' "trdar_codes": [1000002]}')  # 모델이 이웃으로 리셋한 상황
    phase2 = '{"text": "요약", "areas": [{"trdar_code": 1000001, "reason": "이유. 유의할 점: x"}]}'
    interactor, llm, _ = _build(
        monkeypatch, [INTENT_MARKET, phase1_other, phase2],
        conversations=conversations, market=_StubMarket(areas=areas),
    )
    result = await interactor.ask("경쟁 가게는 몇 개나 돼?", conversation_id=100)
    assert [r.id for r in result.recommendations] == ["1000001"]
    # 업종 단서도 없으므로 직전 업종(치킨전문점)을 잇는다 — phase1의 커피-음료 재선택 폐기
    assert result.recommendations[0].category == "치킨전문점"


async def test_사용자가_말한_업종은_phase1_오선택을_이긴다(monkeypatch):
    # 2026-09-01 실측: "길음동 떡볶이집"을 phase1이 커피-음료로 오선택 → 3턴 표류
    services = [ServiceCode(code="CS100010", name="커피-음료"),
                ServiceCode(code="CS100008", name="분식전문점")]
    market = _StubMarket(services=services)
    phase2 = '{"text": "요약", "areas": [{"trdar_code": 1000001, "reason": "이유. 유의할 점: x"}]}'
    interactor, _, _ = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, phase2], market=market)
    result = await interactor.ask("역삼동에서 떡볶이집 괜찮을까?")
    assert result.recommendations[0].category == "분식전문점"  # phase1의 커피-음료 폐기


async def test_정정_신호가_있으면_직전_업종을_승계하지_않는다(monkeypatch):
    services = [ServiceCode(code="CS100010", name="커피-음료"),
                ServiceCode(code="CS100008", name="분식전문점")]
    conversations = _StubConversations(history=[
        Message(id=1, conversation_id=100, role="user", content="역삼동 어때?",
                created_at=_NOW, payload=None),
        Message(id=2, conversation_id=100, role="assistant", content="상권 추천",
                created_at=_NOW,
                payload={"recommendations": [
                    {"id": "1000001", "name": "테스트상권",
                     "serviceCode": "CS100010", "category": "커피-음료"}]}),
    ])
    market = _StubMarket(services=services)
    phase2 = '{"text": "요약", "areas": [{"trdar_code": 1000001, "reason": "이유. 유의할 점: x"}]}'
    interactor, _, _ = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, phase2],
        conversations=conversations, market=market,
    )
    result = await interactor.ask("엥 나는 떡볶이집을 추천해달라고 했는데?", conversation_id=100)
    assert result.recommendations[0].category == "분식전문점"  # 감지가 승계를 이긴다


async def test_업종_단서가_있으면_phase1_업종을_신뢰한다(monkeypatch):  # 무손상
    areas = [
        AreaInfo(trdar_code=1000001, trdar_name="테스트상권", district_name="강남구",
                 adm_dong_name="역삼동", lat=37.5, lng=127.0),
    ]
    conversations = _StubConversations(history=[
        Message(id=1, conversation_id=100, role="user", content="강남 상권 어때?",
                created_at=_NOW, payload=None),
        Message(id=2, conversation_id=100, role="assistant", content="상권 추천",
                created_at=_NOW,
                payload={"recommendations": [
                    {"id": "1000001", "name": "테스트상권",
                     "serviceCode": "CS100001", "category": "치킨전문점"}]}),
    ])
    phase2 = '{"text": "요약", "areas": [{"trdar_code": 1000001, "reason": "이유. 유의할 점: x"}]}'
    interactor, _, _ = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, phase2],
        conversations=conversations, market=_StubMarket(areas=areas),
    )
    result = await interactor.ask("카페는 포화 아니야?", conversation_id=100)
    assert result.recommendations[0].category == "커피-음료"  # phase1 선택 유지


async def test_랭킹_결정론_응답도_후속_앵커를_남긴다(monkeypatch):
    # 3차 실측 P3: "그 중 첫 번째" 후속이 이어받을 payload가 없어 총신대입구로 리셋됐다
    ranking = [_ranking_row(trdar_code=7, trdar_name="A상권")]
    market = _StubMarket(ranking=ranking)
    interactor, _, stubs = _build(monkeypatch, [INTENT_MARKET], market=market)
    await interactor.ask("유동인구 많고 폐업률 낮은 상권 3곳 추천해줘")
    assert stubs["conversations"].saved[-1][0] == "assistant"
    assert stubs["conversations"].payloads[-1] == {"rankingCodes": [7]}


async def test_구어_메타_질문도_결정론으로_가로챈다(monkeypatch):
    # 3차 실측 P1: "너네 신호 지난달에 몇 개나 맞았는데?"가 새어나가 Gemini가
    # "저는 OpenAI에서 개발한…"이라고 자기 부정했다.
    interactor, llm, _ = _build(monkeypatch, [])
    result = await interactor.ask("너네 신호 지난달에 몇 개나 맞았는데? 증거 보여줘")
    assert llm.calls == []
    assert "Wilson 95% 신뢰구간 하한" in result.text


async def test_general_답변에는_자기_정체성_프리앰블이_붙는다(monkeypatch):
    intent = '{"intent": "general", "stock_query": ""}'
    interactor, _, stubs = _build(monkeypatch, [intent])
    await interactor.ask("점심 뭐 먹을까?")
    assert "redoceanmap" in stubs["gemini"].prompts[0]
    assert "점심 뭐 먹을까?" in stubs["gemini"].prompts[0]


async def test_급등주_찍기_질문은_결정론으로_거절한다(monkeypatch):
    # 3차 실측 P5: market_news로 낙하해 특정 종목을 "단기 투자 기회"로 서술했다
    interactor, llm, _ = _build(monkeypatch, [])
    result = await interactor.ask("오늘 급등할 종목 하나만 찍어줘")
    assert llm.calls == []
    assert "특정 종목을 찍어드리지는 않아요" in result.text
    assert "가격 도달 알림" in result.text


async def test_리졸버_실패_경로에도_미지원_고지가_붙는다(monkeypatch):
    # 3차 실측 P4: "PER 낮은 5개"가 리졸버에서 죽으면 고지 없이 오류 원문만 나갔다
    intent = '{"intent": "stock", "stock_query": "PER 낮은 저평가 국내 주식 5개"}'
    interactor, _, _ = _build(monkeypatch, [intent], stocks=_StubStocks(fail=True))
    result = await interactor.ask("PER 낮은 저평가 국내 주식 5개만 골라줘")
    assert result.text.startswith("※ 종목 간 PER 비교·스크리닝은 아직 지원하지 않아요")


async def test_이유_없는_추천은_내보내지_않는다(monkeypatch):
    # 4차 실측: 프롬프트 의무에도 모델이 상권 일부만 서술(빈 reason 33%) —
    # 서술 없는 추천 카드는 사용자에게 "이유 없는 추천"이라 자른다.
    areas = [
        AreaInfo(trdar_code=1000001, trdar_name="테스트상권", district_name="강남구",
                 adm_dong_name="역삼동", lat=37.5, lng=127.0),
        AreaInfo(trdar_code=1000002, trdar_name="이웃상권", district_name="강남구",
                 adm_dong_name="역삼동", lat=37.4, lng=127.0),
    ]
    phase1_both = ('{"service_code": "CS100010", "service_name": "커피-음료",'
                   ' "trdar_codes": [1000001, 1000002]}')
    interactor, _, _ = _build(
        monkeypatch, [INTENT_MARKET, phase1_both, PHASE2_JSON],  # 1000001만 서술
        market=_StubMarket(areas=areas),
    )
    result = await interactor.ask("역삼동 카페 어때?")
    assert [r.id for r in result.recommendations] == ["1000001"]


async def test_전부_서술이_없으면_추천을_유지한다(monkeypatch):  # 열화 동작
    phase2_no_areas = '{"text": "요약만 있음", "areas": []}'
    interactor, _, _ = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, phase2_no_areas])
    result = await interactor.ask("역삼동 카페 어때?")
    assert len(result.recommendations) == 1  # 이유는 비지만 답변 자체는 살린다


async def test_상권_컨텍스트에_서울_평균_대비_종합점수가_주입된다(monkeypatch):
    market = _StubMarket(scores={1000001: _area_score()})
    interactor, llm, _ = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON], market=market,
    )
    await interactor.ask("역삼동 카페 어때?")
    phase2_prompt = llm.calls[2][0]
    assert "서울 평균 대비: 종합 59.6점·보통 (50점=서울 평균, 이 상권은 평균 상회)" in phase2_prompt
    # 컴포넌트마다 평균 대비 방향을 코드가 못박는다(1-1 실측: 방향 없이 주면 모델이 뒤집는다)
    assert "매출 성장 91.9점(서울 평균 상회 — 상권 +21.9% vs 서울 +5.2%)" in phase2_prompt
    assert "영업 지속성 16.1점(서울 평균 미달)" in phase2_prompt
    assert market.score_calls == [[1000001]]


async def test_종합점수가_없는_상권은_점수_라인을_생략한다(monkeypatch):  # 무손상
    interactor, llm, _ = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON])
    await interactor.ask("역삼동 카페 어때?")
    assert "- 서울 평균 대비:" not in llm.calls[2][0]  # 규칙 문구가 아닌 컨텍스트 라인 기준


async def test_주의_등급_상권은_추천_어휘가_차단되고_등급_고지가_문두에_붙는다(monkeypatch):
    # 2026-08-31 프로덕션 실측(p04): 44.9점 '주의'를 "강력히 추천"으로 사실 반전 서술
    caution = AreaScoreInfo(
        total=44.9, grade="주의",
        components=(
            AreaScoreComponent(key="floating_growth", name="유동인구 성장",
                               score=47.9, value=-0.11, benchmark=0.72),
        ),
    )
    market = _StubMarket(scores={1000001: caution})
    phase2 = ('{"text": "테스트상권을 강력히 추천합니다", "areas": [{"trdar_code": 1000001,'
              ' "reason": "강력히 추천합니다. 유의할 점: 경쟁 밀집."}]}')
    interactor, llm, _ = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, phase2], market=market,
    )
    result = await interactor.ask("역삼동 카페 어때?")

    # 등급 고지가 답변 첫 문단에 코드로 박힌다
    assert result.text.startswith("※ 테스트상권 상권은 종합 44.9점 '주의' 등급")
    # 추천 어휘는 본문·이유 모두에서 차단된다(eval_scorer grade_caution과 같은 어휘)
    assert "추천" not in result.text and "강력히" not in result.text
    assert "추천" not in result.recommendations[0].reason
    assert "유의할 점: 경쟁 밀집." in result.recommendations[0].reason  # 문장은 살린다
    # 컨텍스트에도 방향이 박힌다 — 미달 점수를 "상회"로 뒤집을 수 없게
    assert "유동인구 성장 47.9점(서울 평균 미달 — 상권 -0.1% vs 서울 +0.7%)" in llm.calls[2][0]


def _ranking_row(**overrides) -> AreaRankingInfo:
    base = dict(trdar_code=1, trdar_name="A상권", district_name="강남구", dong_name="역삼동",
                monthly_sales=3_000_000_000, store_count=40, sales_per_store=75_000_000,
                closure_rate=0.0, change_indicator_name="정체")
    return AreaRankingInfo(**{**base, **overrides})


async def test_조건_질의는_LLM_없이_랭킹으로_결정론_응답한다(monkeypatch):
    # 2026-08-31 실측 m4: "유동인구 많고 폐업률 낮은 상권 3곳" → 62초 뒤 422 원문 노출
    ranking = [
        _ranking_row(trdar_code=1, trdar_name="A상권", closure_rate=0.0,
                     monthly_sales=3_000_000_000),
        _ranking_row(trdar_code=2, trdar_name="B상권", closure_rate=2.0,
                     monthly_sales=10_000_000_000),
        _ranking_row(trdar_code=3, trdar_name="C상권", closure_rate=0.0,
                     monthly_sales=8_000_000_000),
        _ranking_row(trdar_code=4, trdar_name="극단상권", closure_rate=0.0,
                     store_count=2),  # 점포 극단값 컷
    ]
    market = _StubMarket(ranking=ranking)
    interactor, llm, _ = _build(monkeypatch, [INTENT_MARKET], market=market)
    result = await interactor.ask("유동인구 많고 폐업률 낮은 상권 3곳 추천해줘")

    assert len(llm.calls) == 1  # phase0만 — phase1·phase2 LLM 미호출
    # 폐업률 낮은 순, 동률은 월매출 높은 순: C(0%, 80억) → A(0%, 30억) → B(2%, 100억)
    lines = result.text.split("\n")
    assert lines[1].startswith("1. C상권") and "폐업률 0% · 월매출 80.0억원" in lines[1]
    assert lines[2].startswith("2. A상권")
    assert lines[3].startswith("3. B상권")
    assert "극단상권" not in result.text
    # 없는 축은 없다고 말한다(I-12) — 유동인구를 정렬한 척하지 않는다
    assert "유동인구 순 정렬은 아직 지원하지 않아" in result.text
    assert result.recommendations == []


async def test_지역이_언급된_조건_질의는_기존_흐름을_탄다(monkeypatch):  # 무손상
    interactor, llm, _ = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON])
    result = await interactor.ask("역삼동에서 폐업률 낮은 카페 어때?")
    assert len(llm.calls) == 3  # phase0·1·2 정상 경유
    assert len(result.recommendations) == 1


async def test_추이_질문은_분기_추이와_산출_방식이_컨텍스트에_주입된다(monkeypatch):
    # I-20, 2026-08-31 실측 p04: "분기 매출 추이 데이터" 요청에 151자 일반 추천
    score = AreaScoreInfo(
        total=59.6, grade="보통",
        components=(AreaScoreComponent(key="sales_growth", name="매출 성장",
                                       score=91.9, value=21.9, benchmark=5.2),),
        trend=(
            AreaTrendPoint(year_quarter=20244, monthly_sales=320_000_000, sales_qoq=None,
                           total_floating_pop=1_230_000, floating_qoq=None),
            AreaTrendPoint(year_quarter=20251, monthly_sales=350_000_000, sales_qoq=9.4,
                           total_floating_pop=1_180_000, floating_qoq=-4.1),
        ),
    )
    market = _StubMarket(scores={1000001: score})
    interactor, llm, _ = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON], market=market,
    )
    await interactor.ask("역삼동 카페 분기 매출 추이 데이터 보여줘")
    context = llm.calls[2][0]
    assert "- 분기 추이: 20244 매출 3.2억(QoQ -) 유동 123.0만(QoQ -)" in context
    assert "20251 매출 3.5억(QoQ +9.4%) 유동 118.0만(QoQ -4.1%)" in context
    assert "[종합점수 산출 방식]" in context


async def test_일반_질문에는_분기_추이를_주입하지_않는다(monkeypatch):  # 프롬프트 예산 보호
    score = AreaScoreInfo(
        total=59.6, grade="보통", components=(),
        trend=(AreaTrendPoint(year_quarter=20251, monthly_sales=350_000_000),),
    )
    market = _StubMarket(scores={1000001: score})
    interactor, llm, _ = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON], market=market,
    )
    await interactor.ask("역삼동 카페 어때?")
    assert "- 분기 추이:" not in llm.calls[2][0]
    assert "[종합점수 산출 방식]" not in llm.calls[2][0]


async def test_중립_방향_답변에는_가격_알림_안내가_붙는다(monkeypatch):
    # [6] — 중립 답변의 공식 대체재(예측 대신 사용자 설정 조건의 사실 통지)
    interactor, _, _ = _build(monkeypatch, [INTENT_STOCK, "주식 서술."])
    result = await interactor.ask("삼성전자 어때?")  # _analysis 기본 direction=NEUTRAL
    assert "'가격 도달 알림'에서 조건을 걸어 보세요" in result.text


async def test_방향이_있으면_가격_알림_안내를_붙이지_않는다(monkeypatch):
    stocks = _StubStocks(result=_analysis(direction="UP"))
    interactor, _, _ = _build(monkeypatch, [INTENT_STOCK, "주식 서술."], stocks=stocks)
    result = await interactor.ask("삼성전자 어때?")
    assert "가격 도달 알림" not in result.text


async def test_임대료_질문은_미지원_고지가_문두에_붙는다(monkeypatch):
    # I-12, 2026-08-31 실측 m5: 임대료 질문에 임대료 언급 0(모델 회피 서술)
    interactor, _, _ = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON])
    result = await interactor.ask("역삼동 카페 임대료 어때?")
    assert result.text.startswith("※ 임대료·보증금·권리금 데이터는 제공하지 않아요")


async def test_배당_확률_질문은_주식_미지원_고지가_문두에_붙는다(monkeypatch):
    # I-12(q03 배당) + I-17(s4 확률) — 결정론 문두 삽입
    interactor, _, _ = _build(monkeypatch, [INTENT_STOCK, "주식 서술."])
    result = await interactor.ask("삼성전자 배당이랑 오를 확률 알려줘")
    first_block = result.text.split("\n\n")[0]
    assert "배당수익률·배당 이력 데이터는 아직 제공하지 않아요" in first_block
    assert "확률은 단정해서 제시하지 않아요" in first_block
    assert result.text.endswith("투자 판단과 그 결과는 본인 책임입니다.")


async def test_용어_풀이는_질문에_없는_용어에만_붙는다(monkeypatch):
    interactor, _, _ = _build(monkeypatch, [INTENT_STOCK, "수급 유출 우위입니다."])
    result = await interactor.ask("애플 어때?")
    assert "수급(사자·팔자 자금의 흐름)" in result.text


def test_지명_어간은_숫자_낀_행정동을_되살린다():
    # 2026-08-31 실측 p06: "목1동"의 선행 한글 어간이 "목" 1자로 붕괴 → 목동 질문 매칭 탈락
    assert ChatInteractor._place_stem("목1동") == "목동"
    assert ChatInteractor._place_stem("성수1가1동") == "성수"   # 기존 동작 무손상
    assert ChatInteractor._place_stem("테헤란로107길") == "테헤란"  # 기존 동작 무손상


async def test_숫자_낀_행정동_지역도_결정론_가드가_보정한다(monkeypatch):
    areas = [
        AreaInfo(trdar_code=1, trdar_name="목동문화체육센터", district_name="양천구",
                 adm_dong_name="목2동", lat=37.53, lng=126.87),
        AreaInfo(trdar_code=2, trdar_name="강남역", district_name="강남구",
                 adm_dong_name="역삼동", lat=37.49, lng=127.02),
    ]
    market = _StubMarket(areas=areas)
    phase1 = ('{"service_code": "CS100010", "service_name": "커피-음료",'
              ' "trdar_codes": [2]}')  # 모델이 유명 상권으로 쏠린 상황
    phase2 = '{"text": "요약", "areas": [{"trdar_code": 1, "reason": "이유. 유의할 점: 경쟁."}]}'
    interactor, _, _ = _build(monkeypatch, [INTENT_MARKET, phase1, phase2], market=market)
    result = await interactor.ask("목동에서 반찬가게 어때?")
    assert [r.id for r in result.recommendations] == ["1"]


async def test_보통_이상_등급_상권은_추천_어휘를_건드리지_않는다(monkeypatch):  # 무손상
    market = _StubMarket(scores={1000001: _area_score()})  # 59.6점·보통
    phase2 = ('{"text": "테스트상권을 추천합니다", "areas": [{"trdar_code": 1000001,'
              ' "reason": "추천 이유. 유의할 점: 경쟁."}]}')
    interactor, _, _ = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, phase2], market=market,
    )
    result = await interactor.ask("역삼동 카페 어때?")
    assert result.text.startswith("테스트상권을 추천합니다")
    assert "추천 이유" in result.recommendations[0].reason


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


async def test_상권_컨텍스트에_인허가_업소_교체가_주입된다(monkeypatch):
    # 분기 팩트는 "얼마나 있나"만 답한다 — 개업·폐업을 함께 줘야 방향이 읽힌다.
    market = _StubMarket(permit_churn={
        1000001: PermitChurnInfo(months=12, opened=18, closed=7, active=214),
    })
    interactor, llm, stubs = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON], market=market,
    )
    await interactor.ask("역삼동 카페 어때?")

    context = llm.calls[2][0]
    assert "- 인허가 업소 교체(최근 12개월): 개업 18곳 · 폐업 7곳 · 현재 영업중 214곳" in context
    assert stubs["market"].permit_calls == [[1000001]]


async def test_인허가가_없는_상권은_라인을_생략한다(monkeypatch):
    # 상권 매칭이 좌표 근사라 붙은 업소가 없는 상권이 정상적으로 존재한다(열화 동작).
    interactor, llm, _ = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON], market=_StubMarket(),
    )
    await interactor.ask("역삼동 카페 어때?")

    # 프롬프트 규칙에도 같은 문구가 있으므로 데이터 라인 형태로 좁혀 확인한다
    assert "- 인허가 업소 교체(최근" not in llm.calls[2][0]


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


def _refit_report(*, n=89, hits=40, gate_passed=False) -> RefitReportInfo:
    row = RefitCandidateRow(
        up_threshold=0.35, w_rsi=0.4, w_trend=0.0, w_bb=0.4, w_obv=0.0, w_momentum=0.2,
        n=n, hits=hits, hit_rate=hits / n, baseline=0.38, wilson_lower=0.35,
        is_current=True, gate_passed=gate_passed,
    )
    return RefitReportInfo(
        ran_at=_NOW, params={}, gate_horizon=5, promote=False, winner=None, reasons=[],
        boards=[RefitHorizonBoard(horizon_days=5, total=1, baseline_up_rate=0.51,
                                  current=row, rows=[row])],
    )


class _StubRefit:
    def __init__(self, report: RefitReportInfo | None = None, fail: bool = False):
        self.report, self.fail = report, fail

    async def latest(self):
        if self.fail:
            raise RuntimeError("조회 실패")
        return self.report


async def test_자기_시그널_검증_질문은_LLM_없이_재적합_수치로_답한다(monkeypatch):
    # "해당 서비스 측에 데이터를 요구하세요" — 자기 서비스를 제3자 취급한 실사례(2026-08-31 q05)
    interactor, llm, stubs = _build(monkeypatch, [])
    interactor._refit = _StubRefit(_refit_report())
    result = await interactor.ask("너희 UP 시그널의 백테스트 적중률, 표본 수, 신뢰구간이 어떻게 돼?")
    assert llm.calls == []  # LLM에 보내지 않는다 — 결정론 답변
    assert "표본 89건 중 40건 적중" in result.text
    assert "Wilson 하한 35%" in result.text
    assert "게이트 미달이라 답변에 단정 문구를 쓰지 않습니다" in result.text  # 정직한 미달 고지
    assert "미래 수익을 보장하지 않습니다" in result.text


async def test_재적합_조회_실패는_방법론만으로_열화한다(monkeypatch):
    interactor, llm, _ = _build(monkeypatch, [])
    interactor._refit = _StubRefit(fail=True)
    result = await interactor.ask("이 서비스 시그널 검증은 어떻게 해?")
    assert llm.calls == []
    assert "재채점 집계는 준비 중" in result.text
    assert "Wilson 95% 신뢰구간 하한" in result.text  # 방법론은 항상 나간다


async def test_자기_지칭_없는_검증_질문은_기존_경로를_탄다(monkeypatch):  # 보수적 매칭
    interactor, llm, stubs = _build(monkeypatch, [INTENT_STOCK, "주식 서술"])
    await interactor.ask("삼성전자 신호 검증된 거야?")
    assert stubs["stocks"].queries == ["삼성전자"]  # 메타 가로채기 없음


async def test_상권_특정_실패는_오류가_아니라_안내_답변이다(monkeypatch):
    # "목동 반찬가게" 류가 422 원문을 받았다(2026-08-31 프로덕션). 조건 어휘가 있는
    # 질문("유동인구 많은 상권 3곳")은 이제 랭킹 결정론 라우팅이 선점한다(별도 테스트).
    interactor, _, stubs = _build(monkeypatch, [INTENT_MARKET, PHASE1_EMPTY])
    result = await interactor.ask("장사 잘되는 동네 어디야?")
    assert "분석할 상권을 특정하지 못했어요" in result.text
    assert "랭킹" in result.text  # 조건 검색 대안 안내
    assert result.recommendations == []
    assert stubs["conversations"].saved[-1][0] == "assistant"  # 대화 이력에도 남는다


async def test_의도_파싱_실패면_market_폴백(monkeypatch):
    # 파싱 실패는 1회 재시도되므로 두 번 연속 실패해야 폴백이 발동한다
    interactor, _, stubs = _build(
        monkeypatch, ["JSON 아님", "역시 JSON 아님", PHASE1_JSON, PHASE2_JSON]
    )
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


async def test_주식_컨텍스트에_거래_밀집_구간이_주입된다(monkeypatch):
    # 차트가 그리는 매물대와 같은 값을 서술에도 준다. 단 지지/저항으로 부르면 안 된다 —
    # 바로 위 라인에 출처가 다른 지지선·저항선이 이미 있어 섞이면 둘 다 못 믿게 된다.
    stocks = _StubStocks(_analysis(
        volume_poc_low=86000.0, volume_poc_high=88000.0,
        volume_poc_share=0.18, volume_price_position="above",
    ))
    interactor, llm, _ = _build(monkeypatch, [INTENT_STOCK, "서술"], stocks=stocks)
    await interactor.ask("삼성전자 어때?")

    stock_prompt = llm.calls[1][0]
    assert "- 거래 밀집 구간: 86,000~88,000원" in stock_prompt  # 원화는 정수 표기
    assert "전체 거래량의 18%" in stock_prompt
    assert "현재가는 그 위" in stock_prompt
    assert "지지선·저항선이 아님" in stock_prompt


async def test_매물대_산출_불가면_라인을_생략한다(monkeypatch):
    # 표본 부족·가격 범위 없음이면 도메인 서비스가 None을 준다(열화 동작).
    interactor, llm, _ = _build(monkeypatch, [INTENT_STOCK, "서술"])
    await interactor.ask("삼성전자 어때?")
    assert "- 거래 밀집 구간:" not in llm.calls[1][0]


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
    # 배지 밑 근거 한 줄 — 판정만 남고 "왜?"가 비면 배지가 지시문처럼 읽힌다(2026-08-28)
    assert result.stock.basis == "표본 120회 · 95% 구간 53~70%."


async def test_주식_카드_결론은_forecast_없으면_약한_결론으로_열화(monkeypatch):
    # 표본 없음(forecast None)이면 방향은 있어도 "근거는 약합니다"로 — 없는 확신 금지.
    stocks = _StubStocks(result=_analysis(direction="UP", score=0.5))
    interactor, _, _ = _build(
        monkeypatch, [INTENT_STOCK, "서술"], stocks=stocks,
        forecaster=_StubForecast(None),
    )
    result = await interactor.ask("삼성전자 어때?")
    assert "근거는 약합니다" in result.stock.headline
    assert result.stock.basis == "과거 통계로 검증할 표본이 아직 없습니다."


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


def test_원화는_정수_달러는_소수2자리로_표기한다():
    # "지지선인 1,245,729.86원" 노출 실사례(2026-08-31 프로덕션) — 원화 호가에 소수점이 없다
    assert ChatInteractor._price_text(1245729.86, "원") == "1,245,730원"
    assert ChatInteractor._price_text(227.979995, "달러") == "227.98달러"


async def test_지역_평균_결측이면_영업개월_괄호를_생략한다(monkeypatch):
    # "(지역 평균 None개월)" 노출 실사례(2026-08-31 프로덕션)
    interactor, _, _ = _build(monkeypatch, [])
    stats = interactor._format_stats({
        1000001: _raw_stat(
            has_cc=True, operating_months_avg=86, region_operating_months_avg=None,
            closure_months_avg=49, region_closure_months_avg=None,
        )
    }, 20261)
    op_text = stats[1000001]["op_months_text"]
    assert "None" not in op_text
    assert "평균 86개월 영업" in op_text and "49개월 만에 닫음" in op_text


async def test_지역_평균이_있으면_괄호를_병기한다(monkeypatch):  # 무손상 회귀
    interactor, _, _ = _build(monkeypatch, [])
    stats = interactor._format_stats({
        1000001: _raw_stat(
            has_cc=True, operating_months_avg=86, region_operating_months_avg=70,
            closure_months_avg=49, region_closure_months_avg=40,
        )
    }, 20261)
    op_text = stats[1000001]["op_months_text"]
    assert "(지역 평균 70개월)" in op_text and "(지역 평균 40개월)" in op_text


async def test_업종_매출_결측_문구는_축을_명시한다(monkeypatch):
    # 카드 "매출 데이터 없음" vs 점수 페이지 월매출 366억이 모순으로 보였다(2026-08-31 실측)
    interactor, _, _ = _build(monkeypatch, [])
    stats = interactor._format_stats({1000001: _raw_stat()}, 20261)
    assert stats[1000001]["revenue_text"] == "이 업종 매출 데이터 없음"


def test_verdict_파리티_고정():  # www/lib/verdict.ts와 같은 문안이어야 채팅==페이지
    strong = StockForecastSummary(
        signal_direction="UP", ready=True, up_rate=0.62, baseline_up_rate=0.55,
        sample_size=120, hits=74, ci_low=0.53, ci_high=0.70,
    )
    head, _ = verdict("UP", strong)
    assert head == "상승 쪽 신호이고, 과거 이 신호일 때 실제로 올랐던 비율이 평소보다 +7%p 높았습니다"

    # 하락도 같은 모양 — up_rate가 '그 방향의 적중률'이라 우위는 양수다(2026-08-28)
    bearish = StockForecastSummary(
        signal_direction="DOWN", ready=True, up_rate=0.45, baseline_up_rate=0.30,
        sample_size=200, hits=90, ci_low=0.38, ci_high=0.52,
    )
    head_down, _ = verdict("DOWN", bearish)
    assert head_down == "하락 쪽 신호이고, 과거 이 신호일 때 실제로 내렸던 비율이 평소보다 +15%p 높았습니다"

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
    # 정체성 프리앰블(P1)이 붙은 채 전달된다 — 원 질문은 보존
    assert stubs["gemini"].prompts[0].endswith("질문: 카파시가 누구야?")
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
    assert "90,000원" in kr and "90,000.00원" not in kr  # 원화는 정수 표기


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


# --- 프로파일 개인화 주입 (개인화 ⓪) ---

async def test_market_경로에_프로파일_블록이_주입된다(monkeypatch):
    profiles = _StubProfiles(summary=_profile())
    interactor, llm, _ = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON], profiles=profiles,
    )
    await interactor.ask("역삼동 카페 어때?", user_id=7)

    assert profiles.calls == [7]
    context = llm.calls[2][0]  # phase2 프롬프트
    assert "[질문자 프로파일" in context
    assert "안정추구형" in context and "5천만~1억원" in context
    assert "단정하지 말 것" in context  # 예산 적합 단정 금지 규칙 동반


async def test_stock_경로에_프로파일_라인이_주입된다(monkeypatch):
    profiles = _StubProfiles(summary=_profile())
    interactor, llm, _ = _build(
        monkeypatch, [INTENT_STOCK, "주식 서술"], profiles=profiles,
    )
    await interactor.ask("삼성전자 어때?", user_id=7)

    context = llm.calls[1][0]  # 서술 프롬프트
    assert "질문자 투자 프로파일(참고): 안정추구형" in context
    assert "매수/매도 권유" in context  # 투자자문 경계 규칙 동반


async def test_비로그인_미작성_실패는_주입_없이_기존과_동일하다(monkeypatch):  # 열화 3종
    # 비로그인(user_id=None) — 포트 호출 자체가 없다
    profiles = _StubProfiles(summary=_profile())
    interactor, llm, _ = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON], profiles=profiles,
    )
    await interactor.ask("역삼동 카페 어때?")
    assert profiles.calls == []
    assert "[질문자 프로파일" not in llm.calls[2][0]

    # 미작성(None) — 블록 생략
    interactor, llm, _ = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON],
        profiles=_StubProfiles(summary=None),
    )
    await interactor.ask("역삼동 카페 어때?", user_id=7)
    assert "[질문자 프로파일" not in llm.calls[2][0]

    # 조회 실패 — 답변 자체는 살린다
    interactor, llm, _ = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON],
        profiles=_StubProfiles(fail=True),
    )
    result = await interactor.ask("역삼동 카페 어때?", user_id=7)
    assert len(result.recommendations) == 1
    assert "[질문자 프로파일" not in llm.calls[2][0]


# --- 출처 인용 주입 (R4) ---

async def test_stock_컨텍스트에_근거_번호와_인용_규칙이_들어간다(monkeypatch):
    news = _StubNewsSearch(hits=[_hit(title="헤드라인과 다른 새 기사")])
    interactor, llm, _ = _build(monkeypatch, [INTENT_STOCK, "주식 서술"], news=news)
    await interactor.ask("삼성전자 어때?")

    ctx = llm.calls[1][0]
    assert "— 근거 [1]" in ctx                      # 시세·지표 블록
    assert "- 근거 [4] 뉴스 감성" in ctx            # 감성·헤드라인 블록
    assert "근거 [5] (" in ctx                      # 관련 뉴스 첫 항목
    assert "근거 번호를 [1]처럼" in ctx             # 프롬프트 인용 규칙 동반


async def test_market_news_컨텍스트에_뉴스별_근거_번호가_붙는다(monkeypatch):
    news = _StubNewsSearch(hits=[_hit(), _hit(title="두 번째 기사")])
    interactor, llm, _ = _build(monkeypatch, [INTENT_MARKET_NEWS, "업황 서술"], news=news)
    await interactor.ask("반도체 업황 어때?")

    ctx = llm.calls[1][0]
    assert "- 근거 [1] (" in ctx and "- 근거 [2] (" in ctx
    assert "근거가 된 뉴스 번호를 [1]처럼" in ctx


# --- I-10 반경·전년대비 질의 가드 ---


def test_반경_파싱은_거리와_단위_표현만_인정한다():
    parse = ChatInteractor._parse_radius_m
    assert parse("강남역 반경 500m 카페") == 500
    assert parse("성수역 1km 이내 카페 어때") == 1000
    assert parse("500미터 근처 샐러드 가게") == 500
    assert parse("홍대 근처 카페 어때") is None      # 단위 없는 근접 표현은 반경이 아니다
    assert parse("30m 도로변 상가 어때") is None      # 50m 미만 — 도로 폭 오탐 차단
    assert parse("2호선 성수역 어때") is None


async def test_반경_질의는_중심_상권_반경_안으로_후보를_제한한다(monkeypatch):
    areas = [
        AreaInfo(trdar_code=1, trdar_name="성수역 골목", district_name="성동구",
                 adm_dong_name="성수동", lat=37.5, lng=127.0,
                 x_coord=200_000, y_coord=450_000),
        AreaInfo(trdar_code=2, trdar_name="가까운골목", district_name="성동구",
                 adm_dong_name="성수동", lat=37.5, lng=127.0,
                 x_coord=200_300, y_coord=450_000),   # 300m — 반경 안
        AreaInfo(trdar_code=3, trdar_name="먼동네", district_name="성동구",
                 adm_dong_name="성수동", lat=37.5, lng=127.0,
                 x_coord=203_000, y_coord=450_000),   # 3,000m — 반경 밖
    ]
    phase1 = '{"service_code": "CS100010", "service_name": "커피-음료", "trdar_codes": [3]}'
    phase2 = ('{"text": "요약", "areas": ['
              '{"trdar_code": 1, "reason": "이유. 유의할 점: 경쟁."},'
              '{"trdar_code": 2, "reason": "이유. 유의할 점: 경쟁."}]}')
    interactor, llm, deps = _build(
        monkeypatch, [INTENT_MARKET, phase1, phase2], market=_StubMarket(areas=areas))

    res = await interactor.ask("성수역 반경 500m 카페 어때?")

    codes = {int(r.id) for r in res.recommendations}
    assert codes == {1, 2}                      # phase1이 고른 3(3km 밖)은 코드로 제거
    assert res.text.startswith("※ '성수역 골목' 중심 반경 500m")  # 결정론 안내 문두


async def test_반경_기준점을_못_찾으면_미적용을_명시하고_기존_흐름을_유지한다(monkeypatch):
    # 자치구 어간("강남")만 매칭되고 상권명 낱말 매칭이 없다 — 중심 특정 불가
    areas = [AreaInfo(trdar_code=1000001, trdar_name="테스트상권", district_name="강남구",
                      adm_dong_name="역삼동", lat=37.5, lng=127.0,
                      x_coord=200_000, y_coord=450_000)]
    interactor, llm, deps = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON],
        market=_StubMarket(areas=areas))

    res = await interactor.ask("강남 반경 500m 카페 어때?")

    assert res.text.startswith("※ 반경 500m 조건은 기준 지점을")   # 미적용 명시
    assert [r.id for r in res.recommendations] == ["1000001"]      # 기존 흐름 무손상


async def test_phase1_표에_전년동분기_대비_열이_들어간다(monkeypatch):
    interactor, llm, deps = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON],
        market=_StubMarket(yoy={1000001: 12.5}))

    await interactor.ask("역삼동 카페 어때?")

    phase1_prompt = llm.calls[1][0]
    assert "매출전년동분기대비(%)" in phase1_prompt
    assert "|+12.5|" in phase1_prompt


async def test_상권변화지표_해석이_상권_성격에_주입된다(monkeypatch):  # I-1
    insights = {1000001: (
        AreaInsight(key="customer_gender", tone="neutral", text="성별 문장"),
        AreaInsight(key="change_indicator", tone="warning",
                    text="상권변화지표 '상권축소' — 신규 진입에 불리합니다."),
    )}
    interactor, llm, deps = _build(
        monkeypatch, [INTENT_MARKET, PHASE1_JSON, PHASE2_JSON],
        market=_StubMarket(insights=insights))

    await interactor.ask("역삼동 카페 어때?")

    phase2_prompt = llm.calls[2][0]
    assert "상권변화지표 '상권축소'" in phase2_prompt


# --- B2 영향 키워드 ---


async def test_영향_키워드가_컨텍스트와_카드에_실린다(monkeypatch):
    keywords = [
        NewsKeyword(keyword="실적", count=5, sentiment_avg=0.4, sample_title="실적 서프라이즈"),
        NewsKeyword(keyword="리콜", count=3, sentiment_avg=-0.5, sample_title="리콜 발표"),
        NewsKeyword(keyword="합병", count=2, sentiment_avg=0.05, sample_title="합병 검토"),
    ]
    interactor, llm, deps = _build(
        monkeypatch, [INTENT_STOCK, "주식 답변"], news=_StubNewsSearch(keywords=keywords))

    res = await interactor.ask("삼성전자 어때?")

    context = llm.calls[1][0]
    assert "영향 키워드(근거 [4]" in context
    assert "실적(5건·호재쪽)" in context
    assert "리콜(3건·악재쪽)" in context
    assert "합병(2건)" in context          # 감성 기울기 미달 — 방향 표기 없음
    assert res.stock.keywords == ["실적", "리콜", "합병"]


async def test_키워드_표본_미달이면_라인과_카드가_비어있다(monkeypatch):  # 열화
    interactor, llm, deps = _build(monkeypatch, [INTENT_STOCK, "주식 답변"])
    res = await interactor.ask("삼성전자 어때?")
    assert "영향 키워드" not in llm.calls[1][0]
    assert res.stock.keywords == []


async def test_phase2가_reason을_빼먹어도_500이_아니라_열화한다(monkeypatch):
    # 4차 실측 M8 t1: reason 키 누락 → KeyError → 500
    phase2_no_reason = '{"text": "요약", "areas": [{"trdar_code": 1000001}]}'
    interactor, _, _ = _build(monkeypatch, [INTENT_MARKET, PHASE1_JSON, phase2_no_reason])
    result = await interactor.ask("역삼동 카페 어때?")
    assert result.recommendations  # 예외 없이 추천이 나간다


async def test_알림_사용법_질문은_결정론으로_답한다(monkeypatch):
    # 4차 실측 S1 t5·S9 t5: Gemini가 "종 모양 아이콘"·"권리금 변동 알림"을 지어냄
    interactor, _, _ = _build(monkeypatch, [])  # LLM 호출이 있으면 소진 실패로 드러난다
    result = await interactor.ask("가격 알림 설정은 어떻게 해?")
    assert "가격 도달 알림" in result.text
    assert "임대료·권리금" in result.text  # 상권 알림 부재를 명시


async def test_급등할_종목_요구도_결정론_거절이다(monkeypatch):
    # 4차 실측 S4 t1: 관형형 어미(급등"할") 때문에 정규식을 빠져나가 market_news로 낙하
    interactor, _, _ = _build(monkeypatch, [])
    result = await interactor.ask("내일 급등할 종목 알려줘")
    assert "찍어드리지는 않아요" in result.text
    result2 = await interactor.ask("아 그러지 말고 하나만 찍어줘")
    assert "찍어드리지는 않아요" in result2.text
