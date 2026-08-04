from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from game.adapter.outbound.orm.game_community_comment_orm import GameCommunityCommentOrm
from game.adapter.outbound.orm.game_community_post_orm import GameCommunityPostOrm
from game.adapter.outbound.orm.game_community_report_orm import GameCommunityReportOrm
from game.adapter.outbound.orm.game_position_orm import GamePositionOrm
from game.app.ports.output.community_moderation_repository import (
    CommunityModerationRepositoryPort,
    ReportedRecord,
)
from game.app.ports.output.community_repository import (
    CommentRecord,
    CommunityRepositoryPort,
    PostRecord,
)


def _post(row: GameCommunityPostOrm) -> PostRecord:
    return PostRecord(
        id=row.id,
        user_id=row.user_id,
        symbol=row.symbol,
        body=row.body,
        created_tick=row.created_tick,
        created_at=row.created_at,
    )


def _comment(row: GameCommunityCommentOrm) -> CommentRecord:
    return CommentRecord(
        id=row.id,
        post_id=row.post_id,
        user_id=row.user_id,
        body=row.body,
        created_tick=row.created_tick,
        created_at=row.created_at,
    )


class CommunityPgRepository(CommunityRepositoryPort, CommunityModerationRepositoryPort):
    """토론방 영속.

    **살아 있는 행의 정의가 한 곳에만 있다** — `_alive()`. 본인 삭제(`deleted_at`)와
    어드민 숨김(`hidden_at`)을 조회마다 다시 적으면 새 조회 경로에서 빠뜨리게 되고,
    그러면 내린 글이 어딘가에서 다시 보인다.

    포트는 둘(사용자용·운영용)인데 구현이 하나인 이유: 두 포트가 같은 세 테이블을 만지고,
    특히 위의 `_alive()` 불변식을 공유한다. 클래스를 나누면 그 정의가 두 벌이 된다.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _alive(model):
        """내려가지 않은 행 조건. 글·댓글이 같은 두 컬럼을 쓴다."""
        return (model.deleted_at.is_(None)) & (model.hidden_at.is_(None))

    async def list_posts(self, symbol: str, epoch_id: int, limit: int) -> list[PostRecord]:
        rows = (
            await self._session.execute(
                select(GameCommunityPostOrm)
                .where(
                    GameCommunityPostOrm.symbol == symbol,
                    GameCommunityPostOrm.epoch_id == epoch_id,
                    self._alive(GameCommunityPostOrm),
                )
                .order_by(GameCommunityPostOrm.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
        return [_post(r) for r in rows]

    async def list_comments(self, post_ids: list[int]) -> list[CommentRecord]:
        if not post_ids:
            return []
        rows = (
            await self._session.execute(
                select(GameCommunityCommentOrm)
                .where(
                    GameCommunityCommentOrm.post_id.in_(post_ids),
                    self._alive(GameCommunityCommentOrm),
                )
                .order_by(GameCommunityCommentOrm.created_at.asc())
            )
        ).scalars().all()
        return [_comment(r) for r in rows]

    async def find_post(self, post_id: int) -> PostRecord | None:
        row = (
            await self._session.execute(
                select(GameCommunityPostOrm).where(
                    GameCommunityPostOrm.id == post_id,
                    self._alive(GameCommunityPostOrm),
                )
            )
        ).scalar_one_or_none()
        return _post(row) if row else None

    async def add_post(
        self, user_id: int, symbol: str, epoch_id: int, body: str, tick: int
    ) -> PostRecord:
        row = GameCommunityPostOrm(
            user_id=user_id,
            symbol=symbol,
            epoch_id=epoch_id,
            body=body,
            created_tick=tick,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _post(row)

    async def add_comment(
        self, user_id: int, post_id: int, epoch_id: int, body: str, tick: int
    ) -> CommentRecord:
        row = GameCommunityCommentOrm(
            user_id=user_id,
            post_id=post_id,
            epoch_id=epoch_id,
            body=body,
            created_tick=tick,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _comment(row)

    async def soft_delete_post(self, user_id: int, post_id: int) -> bool:
        # 작성자 일치를 WHERE에 넣는다 — 조회 후 비교하면 그 사이에 바뀔 수 있고,
        # 무엇보다 "남의 글"과 "없는 글"이 같은 결과가 되어 존재 여부가 새지 않는다.
        result = await self._session.execute(
            update(GameCommunityPostOrm)
            .where(
                GameCommunityPostOrm.id == post_id,
                GameCommunityPostOrm.user_id == user_id,
                self._alive(GameCommunityPostOrm),
            )
            .values(deleted_at=func.now())
        )
        await self._session.commit()
        return result.rowcount > 0

    async def soft_delete_comment(self, user_id: int, comment_id: int) -> bool:
        result = await self._session.execute(
            update(GameCommunityCommentOrm)
            .where(
                GameCommunityCommentOrm.id == comment_id,
                GameCommunityCommentOrm.user_id == user_id,
                self._alive(GameCommunityCommentOrm),
            )
            .values(deleted_at=func.now())
        )
        await self._session.commit()
        return result.rowcount > 0

    async def add_report(
        self, reporter_user_id: int, target_type: str, target_id: int, reason: str
    ) -> None:
        # 중복 신고는 유니크 제약이 막는다. 조회 후 분기하면 동시 요청 둘이 통과한다.
        await self._session.execute(
            pg_insert(GameCommunityReportOrm)
            .values(
                reporter_user_id=reporter_user_id,
                target_type=target_type,
                target_id=target_id,
                reason=reason,
            )
            .on_conflict_do_nothing(
                constraint="uq_game_community_reports_target_reporter"
            )
        )
        await self._session.commit()

    # ── 운영(어드민) — CommunityModerationRepositoryPort ──────────────────────────

    def _model(self, target_type: str):
        if target_type == "post":
            return GameCommunityPostOrm
        if target_type == "comment":
            return GameCommunityCommentOrm
        raise ValueError(f"알 수 없는 대상 유형입니다: {target_type}")

    async def list_reported(self, limit: int) -> list[ReportedRecord]:
        """신고가 쌓인 글·댓글. 신고 테이블을 축으로 잡고 본문을 붙인다.

        신고는 글·댓글을 한 테이블에서 받으므로(FK 없음) 본문 조인을 유형별로 나눠 두 번
        돌린 뒤 최근 신고순으로 합친다 — 한 쿼리로 만들려면 UNION에 컬럼을 맞춰야 하는데
        대기줄 크기(limit)가 작아 값이 없다.
        """
        grouped = (
            select(
                GameCommunityReportOrm.target_type,
                GameCommunityReportOrm.target_id,
                func.count().label("report_count"),
                func.array_agg(GameCommunityReportOrm.reason).label("reasons"),
                func.max(GameCommunityReportOrm.created_at).label("reported_at"),
            )
            .group_by(GameCommunityReportOrm.target_type, GameCommunityReportOrm.target_id)
            .order_by(func.max(GameCommunityReportOrm.created_at).desc())
            .limit(limit)
        )
        rows = (await self._session.execute(grouped)).all()
        if not rows:
            return []

        out: list[ReportedRecord] = []
        for target_type, target_id, count, reasons, reported_at in rows:
            if target_type == "post":
                post = (
                    await self._session.execute(
                        select(GameCommunityPostOrm).where(GameCommunityPostOrm.id == target_id)
                    )
                ).scalar_one_or_none()
                if post is None:
                    continue  # 대상이 사라졌다 — 대기줄에서 조용히 뺀다
                symbol, author, body, hidden = (
                    post.symbol,
                    post.user_id,
                    post.body,
                    post.hidden_at is not None,
                )
            else:
                joined = (
                    await self._session.execute(
                        select(GameCommunityCommentOrm, GameCommunityPostOrm.symbol)
                        .join(
                            GameCommunityPostOrm,
                            GameCommunityCommentOrm.post_id == GameCommunityPostOrm.id,
                        )
                        .where(GameCommunityCommentOrm.id == target_id)
                    )
                ).first()
                if joined is None:
                    continue
                comment, symbol = joined
                author, body, hidden = (
                    comment.user_id,
                    comment.body,
                    comment.hidden_at is not None,
                )

            out.append(
                ReportedRecord(
                    target_type=target_type,
                    target_id=target_id,
                    symbol=symbol,
                    author_user_id=author,
                    body=body,
                    report_count=count,
                    reasons=tuple(reasons or ()),
                    reported_at=reported_at,
                    hidden=hidden,
                )
            )
        return out

    async def hide(self, target_type: str, target_id: int, reason: str) -> bool:
        model = self._model(target_type)
        result = await self._session.execute(
            update(model)
            .where(model.id == target_id, model.hidden_at.is_(None))
            .values(hidden_at=func.now(), hidden_reason=reason)
        )
        await self._session.commit()
        return result.rowcount > 0

    async def unhide(self, target_type: str, target_id: int) -> bool:
        model = self._model(target_type)
        result = await self._session.execute(
            update(model)
            .where(model.id == target_id, model.hidden_at.is_not(None))
            .values(hidden_at=None, hidden_reason=None)
        )
        await self._session.commit()
        return result.rowcount > 0

    # ── 사용자용 (이어서) ────────────────────────────────────────────────────────

    async def holders(self, symbol: str, user_ids: list[int], epoch_id: int) -> set[int]:
        if not user_ids:
            return set()
        rows = (
            await self._session.execute(
                select(GamePositionOrm.user_id)
                .where(
                    GamePositionOrm.symbol == symbol,
                    GamePositionOrm.user_id.in_(user_ids),
                    GamePositionOrm.epoch_id == epoch_id,
                    GamePositionOrm.closed_tick.is_(None),  # 열린 포지션만
                )
                .distinct()
            )
        ).scalars().all()
        return set(rows)
