"""QuestionInsightInteractor 테스트 — 스텁 허브 포트로 검증."""
from __future__ import annotations

from datetime import datetime, timezone

from admin.app.dtos.question_insight_dto import QuestionBoardQuery
from admin.app.use_cases.question_insight_interactor import QuestionInsightInteractor
from hub.app.dtos.question_insight_dto import (
    KindCount,
    QuestionInsightStats,
    QuestionRecord,
    RegionDemand,
)

_NOW = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)


class _StubQuestions:
    def __init__(self, stats: QuestionInsightStats,
                 recent: tuple[QuestionRecord, ...] = ()):
        self._stats = stats
        self._recent = recent
        self.stats_calls: list[int] = []
        self.recent_calls: list[int] = []

    async def stats(self, days: int = 30) -> QuestionInsightStats:
        self.stats_calls.append(days)
        return self._stats

    async def recent_questions(self, limit: int = 50) -> tuple[QuestionRecord, ...]:
        self.recent_calls.append(limit)
        return self._recent


def _stats(**overrides) -> QuestionInsightStats:
    base = dict(
        window_days=30, total_questions=10,
        kind_counts=(KindCount(kind="market", count=6), KindCount(kind="stock", count=2)),
        nonseoul_regions=(RegionDemand(region="부산", count=3),),
    )
    return QuestionInsightStats(**{**base, **overrides})


async def test_보드는_기간과_상한을_포트에_그대로_전달한다():
    port = _StubQuestions(_stats())
    board = await QuestionInsightInteractor(port).get_board(
        QuestionBoardQuery(days=7, limit=20)
    )
    assert port.stats_calls == [7]
    assert port.recent_calls == [20]
    assert board.window_days == 30 and board.total_questions == 10


async def test_비중은_답변_총량_분모로_계산한다():
    board = await QuestionInsightInteractor(_StubQuestions(_stats())).get_board(
        QuestionBoardQuery(days=30, limit=50)
    )
    shares = {k.kind: k.share_pct for k in board.kinds}
    assert shares == {"market": 75.0, "stock": 25.0}  # 6/8, 2/8 — 질문 10건이 분모가 아니다


async def test_답변이_없으면_비중은_0이다():
    board = await QuestionInsightInteractor(
        _StubQuestions(_stats(kind_counts=(), total_questions=0))
    ).get_board(QuestionBoardQuery(days=30, limit=50))
    assert board.kinds == ()
    assert board.total_questions == 0


async def test_최근_질문과_서울외_수요를_뷰로_옮긴다():
    recent = (QuestionRecord(conversation_id=1, question="부산 서면 어때?",
                             answer_kind="nonseoul", asked_at=_NOW),)
    board = await QuestionInsightInteractor(
        _StubQuestions(_stats(), recent=recent)
    ).get_board(QuestionBoardQuery(days=30, limit=50))
    assert board.recent[0].question == "부산 서면 어때?"
    assert board.recent[0].answer_kind == "nonseoul"
    assert board.nonseoul_regions[0].region == "부산"
    assert board.nonseoul_regions[0].count == 3
