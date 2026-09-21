"""core/llm/request_queue 검증 — 상한·FIFO·순번 통지·취소 시 자리 누수 없음·점유 시간 상한.

줄이 하나라 자리가 새면 채팅 전체가 멈춘다. 그래서 취소 경로 두 갈래(줄 선 채 취소 /
자리를 넘겨받은 직후 취소)를 따로 확인한다.
"""
import asyncio

import pytest

from core.llm import request_queue as request_queue_module
from core.llm.request_queue import RequestQueue


@pytest.fixture(autouse=True)
def fast_poll(monkeypatch):
    monkeypatch.setattr(request_queue_module, "_POLL_SECONDS", 0.01)


async def _settle() -> None:
    """대기자가 순번을 다시 읽을 만큼 루프를 돌린다."""
    await asyncio.sleep(0.05)


async def test_상한까지는_기다리지_않고_넘으면_도착_순서대로_돈다():
    queue = RequestQueue(1)
    order: list[str] = []
    running = 0
    peak = 0
    gate = asyncio.Event()

    async def job(name: str) -> None:
        nonlocal running, peak
        async with queue.slot():
            running += 1
            peak = max(peak, running)
            order.append(name)
            await gate.wait()
            running -= 1

    tasks = []
    for name in ("a", "b", "c"):
        tasks.append(asyncio.create_task(job(name)))
        await asyncio.sleep(0)  # 도착 순서 고정
    await _settle()
    assert order == ["a"]

    gate.set()
    await asyncio.gather(*tasks)
    assert order == ["a", "b", "c"]
    assert peak == 1


async def test_상한이_2면_두_건이_함께_돈다():
    queue = RequestQueue(2)
    started: list[str] = []
    gate = asyncio.Event()

    async def job(name: str) -> None:
        async with queue.slot():
            started.append(name)
            await gate.wait()

    tasks = [asyncio.create_task(job(n)) for n in ("a", "b", "c")]
    await _settle()
    assert started == ["a", "b"]
    gate.set()
    await asyncio.gather(*tasks)
    assert started == ["a", "b", "c"]


async def test_대기_순번을_알리고_앞이_빠지면_갱신한다():
    queue = RequestQueue(1)
    first_done = asyncio.Event()
    second_done = asyncio.Event()
    seen: list[int] = []

    async def holder(done: asyncio.Event) -> None:
        async with queue.slot():
            await done.wait()

    async def watcher() -> None:
        async with queue.slot(on_wait=seen.append):
            pass

    t1 = asyncio.create_task(holder(first_done))
    await asyncio.sleep(0)
    t2 = asyncio.create_task(holder(second_done))
    await asyncio.sleep(0)
    t3 = asyncio.create_task(watcher())
    await _settle()
    assert seen == [2]

    first_done.set()
    await _settle()
    assert seen == [2, 1]

    second_done.set()
    await asyncio.gather(t1, t2, t3)


async def test_순번이_그대로여도_주기적으로_다시_알린다(monkeypatch):
    monkeypatch.setattr(request_queue_module, "_RENOTIFY_TICKS", 2)
    queue = RequestQueue(1)
    done = asyncio.Event()
    seen: list[int] = []

    async def holder() -> None:
        async with queue.slot():
            await done.wait()

    async def watcher() -> None:
        async with queue.slot(on_wait=seen.append):
            pass

    t1 = asyncio.create_task(holder())
    await asyncio.sleep(0)
    t2 = asyncio.create_task(watcher())
    await _settle()
    assert len(seen) >= 2 and set(seen) == {1}
    done.set()
    await asyncio.gather(t1, t2)


async def test_줄_선_채_취소하면_줄에서_빠지고_자리가_새지_않는다():
    queue = RequestQueue(1)
    done = asyncio.Event()
    ran: list[str] = []

    async def job(name: str, wait: bool) -> None:
        async with queue.slot():
            ran.append(name)
            if wait:
                await done.wait()

    t1 = asyncio.create_task(job("a", True))
    await asyncio.sleep(0)
    t2 = asyncio.create_task(job("b", False))
    await asyncio.sleep(0)
    t3 = asyncio.create_task(job("c", False))
    await _settle()

    t2.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t2
    done.set()
    await asyncio.gather(t1, t3)
    assert ran == ["a", "c"]

    # 자리가 돌아왔는지 — 새 요청이 기다리지 않는다
    await asyncio.wait_for(job("d", False), timeout=0.5)
    assert ran == ["a", "c", "d"]


async def test_자리를_넘겨받은_직후_취소돼도_다음_사람에게_반납한다():
    queue = RequestQueue(1)
    ran: list[str] = []

    async def job(name: str) -> None:
        async with queue.slot():
            ran.append(name)

    await queue._acquire(None)  # 첫 자리를 직접 쥔다
    t2 = asyncio.create_task(job("b"))
    await asyncio.sleep(0)
    t3 = asyncio.create_task(job("c"))
    await _settle()

    queue._release()  # b의 표가 채워진다 — b가 깨어나기 전에 취소
    t2.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t2
    await asyncio.wait_for(t3, timeout=0.5)
    assert ran == ["c"]
    await asyncio.wait_for(job("d"), timeout=0.5)


async def test_점유_시간_상한을_넘으면_끊고_자리를_넘긴다(monkeypatch):
    monkeypatch.setattr(request_queue_module, "_MAX_HOLD_SECONDS", 0.05)
    queue = RequestQueue(1)

    async def hung() -> None:
        async with queue.slot():
            await asyncio.sleep(10)

    with pytest.raises(TimeoutError):
        await hung()

    async def quick() -> str:
        async with queue.slot():
            return "ok"

    assert await asyncio.wait_for(quick(), timeout=0.5) == "ok"
