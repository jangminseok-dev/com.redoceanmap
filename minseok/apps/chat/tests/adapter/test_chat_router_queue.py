"""/chat/ask/progress 대기열 계약 — 동시에 온 두 번째 질문은 stage "queued"로 순번을 받고,
앞 질문이 끝난 뒤에 처리된다. 프론트는 stage 라벨을 그대로 보여주므로 이 이벤트가 화면 문구다.
"""
import asyncio
import json

import httpx
import pytest
from fastapi import FastAPI

from chat.adapter.inbound.api.v1 import chat_router as chat_router_module
from chat.adapter.inbound.api.v1.chat_router import chat_router
from chat.app.dtos.chat_dto import AskResponse
from chat.dependencies.chat_provider import get_chat_use_case
from core.llm import request_queue as request_queue_module
from core.llm.request_queue import RequestQueue
from core.security import get_current_user_id


class _StubChatUseCase:
    """ask만 쓰는 최소 대역 — 첫 질문은 gate가 열릴 때까지 자리를 쥔다."""

    def __init__(self) -> None:
        self.gate = asyncio.Event()
        self.started: list[str] = []
        self.peak = 0
        self._running = 0

    async def ask(self, prompt, conversation_id, *, user_id, on_stage=None) -> AskResponse:
        self._running += 1
        self.peak = max(self.peak, self._running)
        self.started.append(prompt)
        on_stage("intent", "질문을 읽고 있어요")
        await self.gate.wait()
        self._running -= 1
        return AskResponse(text=f"답:{prompt}", recommendations=[], conversationId=1)


def _events(body: str) -> list[dict]:
    return [json.loads(chunk[6:]) for chunk in body.split("\n\n") if chunk.startswith("data: ")]


@pytest.fixture
def stub(monkeypatch):
    monkeypatch.setattr(request_queue_module, "_POLL_SECONDS", 0.01)
    monkeypatch.setattr(chat_router_module, "chat_queue", RequestQueue(1))
    return _StubChatUseCase()


@pytest.fixture
def client(stub):
    app = FastAPI()
    app.include_router(chat_router)
    app.dependency_overrides[get_chat_use_case] = lambda: stub
    app.dependency_overrides[get_current_user_id] = lambda: 1
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_동시에_온_두번째_질문은_대기_순번을_받고_앞_질문_뒤에_처리된다(stub, client):
    async with client:
        first = asyncio.create_task(client.post("/chat/ask/progress", json={"prompt": "첫째"}))
        while not stub.started:
            await asyncio.sleep(0.01)
        second = asyncio.create_task(client.post("/chat/ask/progress", json={"prompt": "둘째"}))
        await asyncio.sleep(0.1)
        assert stub.started == ["첫째"]  # 둘째는 아직 유스케이스에 닿지 않았다

        stub.gate.set()
        res1, res2 = await asyncio.gather(first, second)

    events1, events2 = _events(res1.text), _events(res2.text)
    assert [e["stage"] for e in events1 if e["type"] == "stage"] == ["intent"]
    assert events1[-1]["data"]["text"] == "답:첫째"

    stages2 = [e for e in events2 if e["type"] == "stage"]
    assert stages2[0]["stage"] == "queued"
    assert "대기 1번째" in stages2[0]["label"]
    assert stages2[-1]["stage"] == "intent"  # 대기 뒤에 정상 단계가 이어진다
    assert events2[-1]["data"]["text"] == "답:둘째"
    assert stub.peak == 1


async def test_혼자_온_질문은_대기_이벤트_없이_바로_처리된다(stub, client):
    stub.gate.set()
    async with client:
        res = await client.post("/chat/ask/progress", json={"prompt": "혼자"})
    events = _events(res.text)
    assert [e["stage"] for e in events if e["type"] == "stage"] == ["intent"]
    assert events[-1]["type"] == "result"
