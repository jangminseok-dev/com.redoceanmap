"""langchain_chat_engine_adapter.py — 랭체인(LCEL) 챗봇 엔진 어댑터.

랭체인 import는 이 파일(adapter 계층)에만 있다. app·domain은 `LangchainChatEnginePort`만 본다.
`langchain-ollama`의 ChatOllama를 쓰지 않고 오케스트레이터를 감싼 ChatModel을 직접 만든 이유는
LLM 추론 수렴 규칙(모든 추론은 `llm_orchestrator` 경유)과 단일 모델 정책 때문이다 —
로컬 GPU에서 Ollama 커넥션이 이원화되면 모델이 이중 점유될 수 있다.
"""
from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from core.llm.llm_orchestrator import llm_orchestrator
from hub.app.dtos.langchain_semantic_dto import EngineAnswer, EngineTurn
from hub.app.ports.output.langchain_chat_engine_port import LangchainChatEnginePort

_CHAT_SYSTEM = """너는 상권·창업·주식 질문에 답하는 한국어 비서다.
이전 대화 흐름을 이어서 자연스럽게 답하되, 모르는 것은 모른다고 말한다.
매매 지시나 수익 보장은 하지 않는다. 간결하게 답하라."""

_RAG_SYSTEM = """너는 제공된 [Context]에만 근거해 사실을 전달하는 비서다.
[Context]에 없는 내용을 추측하거나 외부 지식으로 지어내는 것은 절대 허용되지 않는다.
근거가 부족하면 부족하다고 말하라. 한국어로 간결하게 답하라.

[Context]
{context}"""

_CHAT_PROMPT = ChatPromptTemplate.from_messages(
    [("system", _CHAT_SYSTEM), MessagesPlaceholder("history"), ("human", "{question}")]
)
_RAG_PROMPT = ChatPromptTemplate.from_messages(
    [("system", _RAG_SYSTEM), MessagesPlaceholder("history"), ("human", "{question}")]
)


def _split(messages: list[BaseMessage]) -> tuple[str | None, list[dict[str, str]], str]:
    """랭체인 메시지 목록을 오케스트레이터 인자(system·history·prompt)로 나눈다."""
    systems = [str(m.content) for m in messages if isinstance(m, SystemMessage)]
    convo = [m for m in messages if not isinstance(m, SystemMessage)]
    *earlier, last = convo
    history = [
        {
            "role": "assistant" if isinstance(m, AIMessage) else "user",
            "content": str(m.content),
        }
        for m in earlier
    ]
    return ("\n\n".join(systems) or None), history, str(last.content)


class ExaoneChatModel(BaseChatModel):
    """LCEL 체인에 꽂히는 ChatModel — 실제 추론은 `llm_orchestrator`가 한다."""

    @property
    def _llm_type(self) -> str:
        return "exaone-orchestrator"

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None, **kwargs: Any) -> ChatResult:
        raise NotImplementedError("오케스트레이터는 async 전용 — 체인은 ainvoke로 실행한다.")

    async def _agenerate(
        self, messages: list[BaseMessage], stop: list[str] | None = None, **kwargs: Any
    ) -> ChatResult:
        system, history, prompt = _split(messages)
        text = await llm_orchestrator.orchestrate(prompt, system=system, history=history)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])


class LangchainChatEngineAdapter(LangchainChatEnginePort):
    """근거 체인·일반 대화 체인 두 벌을 조립해 두고 턴마다 골라 태운다.

    체인은 `프롬프트 | 모델 | 파서` LCEL 파이프다 — 이 슬라이스에서 랭체인이 실제로 맡는 일은
    프롬프트 조립(이력 주입 포함)과 출력 파싱뿐이고, 분기·가드레일은 인터랙터가 갖는다.
    """

    def __init__(self) -> None:
        model = ExaoneChatModel()
        self._chains = {
            "chat_chain": _CHAT_PROMPT | model | StrOutputParser(),
            "rag_chain": _RAG_PROMPT | model | StrOutputParser(),
        }

    async def converse(self, turn: EngineTurn) -> EngineAnswer:
        chain_name = "rag_chain" if turn.context else "chat_chain"
        payload: dict[str, Any] = {
            "question": turn.prompt,
            "history": [
                AIMessage(content=content)
                if role == "assistant"
                else HumanMessage(content=content)
                for role, content in turn.history
            ],
        }
        if turn.context:
            payload["context"] = turn.context
        answer = await self._chains[chain_name].ainvoke(payload)
        return EngineAnswer(answer=answer.strip(), chain=chain_name)
