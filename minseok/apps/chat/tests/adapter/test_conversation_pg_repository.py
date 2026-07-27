"""get_messages는 '최근' N개를 오래된 순으로 준다.

오름차순 + LIMIT이면 20턴 넘는 대화에서 가장 오래된 20개가 잡혀, 소비자의
`history[-6:]`가 최신이 아닌 과거 턴을 주입한다(직전 상권 코드 승계도 옛 카드를 집는다).
대화가 길수록 맥락이 정확히 뒤집히던 회귀를 고정한다.
"""
from chat.adapter.outbound.pg.conversation_pg_repository import ConversationPgRepository
from chat.adapter.outbound.orm.conversation_orm import MessageOrm


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    """DB 없이 '내림차순 + LIMIT' SQL이 나갔는지와 반환 순서를 본다."""

    def __init__(self, total: int) -> None:
        self._all = [
            MessageOrm(id=i, conversation_id=1, role="user", content=f"턴{i}", payload=None)
            for i in range(1, total + 1)
        ]
        self.stmt = None

    async def execute(self, stmt):
        self.stmt = stmt
        sql = str(stmt)
        # 실제 PG가 그러듯, ORDER BY 방향과 LIMIT을 반영해 돌려준다.
        rows = sorted(self._all, key=lambda m: m.id, reverse="DESC" in sql.upper())
        limit = stmt._limit
        return _FakeResult(rows[:limit] if limit else rows)


async def test_긴_대화에서_최신_20개를_오래된_순으로_준다():
    session = _FakeSession(total=50)
    repo = ConversationPgRepository(session=session)

    msgs = await repo.get_messages(conversation_id=1, limit=20)

    ids = [m.id for m in msgs]
    assert ids == list(range(31, 51)), "최신 20개(31~50)를 오름차순으로 줘야 한다"
    assert ids == sorted(ids), "소비자가 history[-6:]로 자르므로 오래된 순이어야 한다"


async def test_마지막_6턴이_실제로_가장_최신이다():
    """소비자(chat_interactor)의 history[-6:] 관점 — 이 버그의 실제 증상."""
    session = _FakeSession(total=50)
    repo = ConversationPgRepository(session=session)

    recent = (await repo.get_messages(conversation_id=1))[-6:]

    assert [m.content for m in recent] == [f"턴{i}" for i in range(45, 51)]


async def test_메시지가_limit보다_적으면_전부_준다():
    session = _FakeSession(total=3)
    repo = ConversationPgRepository(session=session)

    msgs = await repo.get_messages(conversation_id=1, limit=20)

    assert [m.id for m in msgs] == [1, 2, 3]
