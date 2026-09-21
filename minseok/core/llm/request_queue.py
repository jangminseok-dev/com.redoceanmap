"""채팅 요청 대기열 — 동시 처리 상한 + FIFO 대기.

백엔드 PC의 Ollama는 생성 슬롯이 하나(OLLAMA_NUM_PARALLEL=1, 2026-09-21 실측)라 채팅 두 건이
동시에 들어오면 phase마다 서로의 LLM 호출 뒤에 끼어 **둘 다** 느려지고, 그동안 데이터 수집·리포트
조립까지 겹쳐 PC가 버티지 못한다. 요청 단위로 줄을 세워 앞 질문은 제 속도로 끝내고, 뒷 질문은
자기 순번을 안다.

단일 프로세스·단일 이벤트 루프 전제다(backend replicas 1 · uvicorn 워커 1 —
infra/k8s/base/backend.yaml). 워커를 늘리면 프로세스마다 줄이 따로 생기므로 그때는 Redis로 옮긴다.
LLM 호출 단위가 아니라 요청 단위인 이유: 호출 단위로 막으면 두 질문의 phase가 여전히 번갈아 돌아
대기 순번을 말해줄 수 없다. 같은 프로세스의 /automation 배치와 호스트 cron(label_news)은 이 줄 밖이다.
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from core.config import CHAT_MAX_CONCURRENCY

logger = logging.getLogger("uvicorn.error")

_POLL_SECONDS = 1.0
# 순번이 그대로여도 이 주기로 다시 알린다 — SSE가 오래 침묵하면 중간 프록시(cloudflared·Vercel)가 끊는다.
_RENOTIFY_TICKS = 15
# 한 요청이 자리를 쥘 수 있는 최대 시간 — 줄이 하나라 멈춘 질문(Ollama 무응답) 하나가 뒤를 전부 막는다.
# 정상 질문은 p95 ~1.5분이라 닿지 않는다. 넘으면 TimeoutError로 끊고 자리를 넘긴다.
_MAX_HOLD_SECONDS = 600


class RequestQueue:
    """동시 처리 `limit`건, 나머지는 도착 순서대로 기다린다."""

    def __init__(self, limit: int) -> None:
        self._limit = max(1, limit)
        self._active = 0
        self._waiting: deque[asyncio.Future[None]] = deque()

    @asynccontextmanager
    async def slot(self, on_wait: Callable[[int], None] | None = None) -> AsyncIterator[None]:
        """자리가 날 때까지 기다렸다가 본문을 실행한다. 기다리는 동안 on_wait(대기 순번, 1부터)을 부른다."""
        await self._acquire(on_wait)
        try:
            async with asyncio.timeout(_MAX_HOLD_SECONDS):
                yield
        finally:
            self._release()

    async def _acquire(self, on_wait: Callable[[int], None] | None) -> None:
        # 대기자가 있으면 _active는 항상 상한이다(반납 시 자리를 대기자에게 그대로 넘긴다) — 새치기 불가
        if self._active < self._limit:
            self._active += 1
            return
        ticket: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._waiting.append(ticket)
        logger.info("[chat-queue] 대기 시작 — 순번 %d", len(self._waiting))
        last, ticks = 0, 0
        try:
            while not ticket.done():
                position = self._waiting.index(ticket) + 1
                if on_wait and (position != last or ticks % _RENOTIFY_TICKS == 0):
                    on_wait(position)
                    last = position
                ticks += 1
                await asyncio.wait({ticket}, timeout=_POLL_SECONDS)
        except asyncio.CancelledError:
            if ticket.done():  # 자리를 넘겨받은 직후 취소 — 다음 사람에게 반납
                self._release()
            else:
                self._waiting.remove(ticket)
            raise

    def _release(self) -> None:
        if self._waiting:
            self._waiting.popleft().set_result(None)  # 자리를 그대로 넘긴다(_active 유지)
        else:
            self._active -= 1


# 인스턴스는 하나 — chat 라우터와 허브 랭체인 게이트웨이(ROM 2.0)가 같은 줄에 선다.
chat_queue = RequestQueue(CHAT_MAX_CONCURRENCY)
