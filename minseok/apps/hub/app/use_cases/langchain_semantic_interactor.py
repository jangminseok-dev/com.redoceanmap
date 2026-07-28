from __future__ import annotations

from hub.app.dtos.langchain_semantic_dto import (
    EngineTurn,
    LangchainAskQuery,
    LangchainAskResponse,
    LangchainSemanticQuery,
    LangchainSemanticResponse,
)
from hub.app.ports.input.langchain_semantic_use_case import LangchainSemanticUseCase
from hub.app.ports.output.langchain_chat_engine_port import LangchainChatEnginePort
from hub.app.ports.output.langchain_session_repository import LangchainSessionRepository
from hub.app.ports.output.market_news_search_port import MarketNewsSearchPort
from hub.app.ports.output.semantic_llm_port import SemanticLlmPort
from hub.domain.langchain_chat.session_entity import LangchainSession

_DESTINATIONS = {"crud", "rag", "gemini"}
_HISTORY_TURNS = 10
_NEWS_LIMIT = 4


class LangchainSemanticInteractor(LangchainSemanticUseCase):
    """랭체인 시멘틱 게이트웨이(ROM 2.0) 대장.

    흐름 통제는 여전히 코드가 한다 — 분류(SemanticLlmPort 재사용) → 근거 수집 →
    체인 실행(LangchainChatEnginePort) → 세션 영속. 랭체인은 마지막 답변 생성 한 칸만
    담당하고, 분기·가드레일은 이 인터랙터에 남는다.
    """

    def __init__(
        self,
        llm: SemanticLlmPort,
        engine: LangchainChatEnginePort,
        market_news: MarketNewsSearchPort,
        sessions: LangchainSessionRepository,
    ) -> None:
        self._llm = llm
        self._engine = engine
        self._market_news = market_news
        self._sessions = sessions

    async def ask(self, query: LangchainAskQuery) -> LangchainAskResponse:
        route = await self._llm.classify(query.prompt)
        destination = route.destination if route.destination in _DESTINATIONS else "rag"

        session = await self._resolve_session(query)
        history = await self._sessions.recent_turns(session.id, limit=_HISTORY_TURNS)
        await self._sessions.append_turn(session.id, "user", query.prompt, destination)

        answer, chain = await self._respond(query.prompt, destination, history)
        await self._sessions.append_turn(session.id, "assistant", answer, destination)

        return LangchainAskResponse(
            session_id=session.id,
            destination=destination,
            entities=route.entities,
            answer=answer,
            chain=chain,
        )

    async def _respond(self, prompt, destination, history) -> tuple[str, str]:
        """분류 결과별 답변 생성. 체인을 타지 않는 분기는 체인 이름을 그대로 밝힌다."""
        if destination == "crud":
            return (
                "데이터 조작 의도를 감지했습니다. 실제 실행은 아직 구현되지 않았습니다.",
                "none",
            )

        context = None
        if destination == "rag":
            hits = await self._market_news.search(prompt, limit=_NEWS_LIMIT)
            if not hits:
                # ROM 1.0과 같은 가드레일 — 근거가 없으면 체인을 태우지 않는다(추측 금지)
                return (
                    "관련 정보를 상권 뉴스 코퍼스에서 찾지 못해 답변을 드릴 수 없습니다.",
                    "none",
                )
            context = self._format_context(hits)

        result = await self._engine.converse(
            EngineTurn(
                prompt=prompt,
                destination=destination,
                history=tuple((turn.role, turn.content) for turn in history),
                context=context,
            )
        )
        return result.answer, result.chain

    async def _resolve_session(self, query: LangchainAskQuery) -> LangchainSession:
        """세션이 없거나 남의 것이면 새로 연다 — 세션 id만으로 남의 이력을 읽을 수 없다."""
        if query.session_id is not None:
            found = await self._sessions.get_session(query.session_id)
            if found is not None and found.user_id == query.user_id:
                return found
        return await self._sessions.create_session(user_id=query.user_id)

    @staticmethod
    def _format_context(hits) -> str:
        return "\n".join(
            f"- {hit.title} ({hit.area_tag or '공통'}"
            + (f", {hit.published_at:%Y-%m-%d})" if hit.published_at else ")")
            for hit in hits
        )

    async def introduce_myself(
        self, query: LangchainSemanticQuery
    ) -> LangchainSemanticResponse:
        return LangchainSemanticResponse(
            id=query.id,
            name=query.name,
            introduction="시멘틱 의도 분류 뒤 랭체인(LCEL) 체인으로 답변하는 대화형 "
            "게이트웨이입니다. POST /langchain-semantic/ask 에 prompt와 sessionId를 보내면 "
            "EXAONE 7.8B가 의도를 crud·rag·gemini로 분류하고 — rag는 상권 뉴스를 근거로 "
            "묶은 근거 체인, gemini는 일반 대화 체인을 태웁니다. crud는 감지만 하고 실행하지 "
            "않으며, rag는 근거를 못 찾으면 답변을 거부합니다. 대화는 세션 단위로 이어지고 "
            "최근 10턴이 다음 답변의 이력으로 실립니다. ROM 1.0(/semantic/ask)은 단발 질의로 "
            "그대로 남아 있습니다.",
        )
