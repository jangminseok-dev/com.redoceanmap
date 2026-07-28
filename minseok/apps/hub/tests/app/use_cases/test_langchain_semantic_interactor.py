from datetime import datetime

from hub.app.dtos.langchain_semantic_dto import (
    EngineAnswer,
    LangchainAskQuery,
    LangchainSemanticQuery,
)
from hub.app.dtos.market_news_dto import MarketNewsHit
from hub.app.dtos.semantic_dto import SemanticRoute
from hub.app.use_cases.langchain_semantic_interactor import LangchainSemanticInteractor
from hub.domain.langchain_chat.session_entity import LangchainSession, LangchainTurn


class _StubLlm:
    def __init__(self, route):
        self._route = route

    async def classify(self, question):
        return self._route

    async def answer_grounded(self, question, context):  # ROM 2.0은 쓰지 않는다
        raise AssertionError("랭체인 게이트웨이는 근거 답변도 체인으로 낸다")


class _StubEngine:
    def __init__(self):
        self.turns = []

    async def converse(self, turn):
        self.turns.append(turn)
        chain = "rag_chain" if turn.context else "chat_chain"
        return EngineAnswer(answer=f"체인 답변({chain})", chain=chain)


class _StubNews:
    def __init__(self, hits):
        self._hits = hits

    async def search(self, query, limit=4):
        return self._hits


class _StubSessions:
    """세션 저장소 스텁 — 기존 세션을 미리 심어 소유자 검사도 태울 수 있다."""

    def __init__(self, existing=None, history=()):
        self.sessions = {s.id: s for s in (existing or [])}
        self.appended = []
        self._history = list(history)
        self._next_id = 100

    async def create_session(self, user_id=None):
        session = LangchainSession(id=self._next_id, created_at=datetime(2026, 7, 28), user_id=user_id)
        self.sessions[session.id] = session
        self._next_id += 1
        return session

    async def get_session(self, session_id):
        return self.sessions.get(session_id)

    async def append_turn(self, session_id, role, content, destination=None):
        self.appended.append((session_id, role, content, destination))
        return LangchainTurn(
            id=len(self.appended),
            session_id=session_id,
            role=role,
            content=content,
            created_at=datetime(2026, 7, 28),
            destination=destination,
        )

    async def recent_turns(self, session_id, limit=10):
        return self._history


def _turn(role, content):
    return LangchainTurn(
        id=1, session_id=1, role=role, content=content, created_at=datetime(2026, 7, 28)
    )


def _interactor(route, hits=(), sessions=None, engine=None):
    return LangchainSemanticInteractor(
        llm=_StubLlm(route),
        engine=engine or _StubEngine(),
        market_news=_StubNews(list(hits)),
        sessions=sessions or _StubSessions(),
    )


async def test_rag_분기는_뉴스_근거를_체인_컨텍스트로_넘긴다():
    engine = _StubEngine()
    hits = [MarketNewsHit(title="성수 상권 활황", area_tag="성수", published_at=datetime(2026, 7, 1))]
    result = await _interactor(SemanticRoute("rag", ("성수",)), hits, engine=engine).ask(
        LangchainAskQuery(prompt="성수동 상권 어때?")
    )
    assert result.chain == "rag_chain"
    assert "성수 상권 활황" in engine.turns[0].context


async def test_gemini_분기는_컨텍스트_없이_일반_대화_체인을_탄다():
    result = await _interactor(SemanticRoute("gemini", ())).ask(
        LangchainAskQuery(prompt="피보나치 수열이 뭐야?")
    )
    assert result.destination == "gemini"
    assert result.chain == "chat_chain"


async def test_rag_분기는_근거가_없으면_체인을_태우지_않는다():
    engine = _StubEngine()
    result = await _interactor(SemanticRoute("rag", ()), engine=engine).ask(
        LangchainAskQuery(prompt="어디 상권이 좋아?")
    )
    assert engine.turns == []
    assert result.chain == "none"
    assert "찾지 못해" in result.answer


async def test_crud_분기는_감지만_보고한다():
    result = await _interactor(SemanticRoute("crud", ("추천 기록", "삭제"))).ask(
        LangchainAskQuery(prompt="내 추천 기록 삭제해줘")
    )
    assert result.destination == "crud"
    assert result.chain == "none"


async def test_미지_분류는_rag로_폴백한다():
    result = await _interactor(SemanticRoute("unknown", ())).ask(
        LangchainAskQuery(prompt="아무 질문")
    )
    assert result.destination == "rag"


async def test_이전_턴이_체인_이력으로_실린다():
    engine = _StubEngine()
    sessions = _StubSessions(history=[_turn("user", "안녕"), _turn("assistant", "반가워요")])
    await _interactor(SemanticRoute("gemini", ()), sessions=sessions, engine=engine).ask(
        LangchainAskQuery(prompt="아까 뭐라고 했지?")
    )
    assert engine.turns[0].history == (("user", "안녕"), ("assistant", "반가워요"))


async def test_질문과_답변이_모두_세션에_기록된다():
    sessions = _StubSessions()
    await _interactor(SemanticRoute("gemini", ()), sessions=sessions).ask(
        LangchainAskQuery(prompt="안녕")
    )
    assert [role for _, role, _, _ in sessions.appended] == ["user", "assistant"]


async def test_남의_세션_id로는_이력을_이어받지_못한다():
    남의_세션 = LangchainSession(id=7, created_at=datetime(2026, 7, 28), user_id=999)
    sessions = _StubSessions(existing=[남의_세션])
    result = await _interactor(SemanticRoute("gemini", ()), sessions=sessions).ask(
        LangchainAskQuery(prompt="안녕", session_id=7, user_id=1)
    )
    assert result.session_id != 7


async def test_기존_세션은_그대로_이어진다():
    내_세션 = LangchainSession(id=7, created_at=datetime(2026, 7, 28), user_id=1)
    sessions = _StubSessions(existing=[내_세션])
    result = await _interactor(SemanticRoute("gemini", ()), sessions=sessions).ask(
        LangchainAskQuery(prompt="안녕", session_id=7, user_id=1)
    )
    assert result.session_id == 7


async def test_자기소개는_실기능을_설명한다():
    result = await _interactor(SemanticRoute("rag", ())).introduce_myself(
        LangchainSemanticQuery(id=11, name="랭체인 시멘틱 게이트웨이 (hub/langchain-semantic)")
    )
    assert result.id == 11
    assert "/langchain-semantic/ask" in result.introduction
