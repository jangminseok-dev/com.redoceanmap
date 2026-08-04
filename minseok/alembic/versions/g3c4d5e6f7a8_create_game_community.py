"""종목 토론방 — 글·댓글·신고 (커뮤니티)

Revision ID: g3c4d5e6f7a8
Revises: g2b3c4d5e6f7
Create Date: 2026-08-04

게임의 값은 시각의 함수라 저장하지 않지만(game-harness §1-A) **사람이 쓴 문장**은
난수에서 유도할 수 없어 저장한다 — 관리자 개입·지정가 주문과 같은 성격의 예외다.

작성자 이름은 **저장하지 않는다.** `domain/community/nickname.py`가 user_id에서 결정론으로
유도한다 — `users.name`은 가입 실명이라 공개 토론방에 띄우면 게임 참여가 곧 실명 공개가 된다.

내리는 경로가 둘이고 컬럼이 분리돼 있다:
- `deleted_at` — 작성자 본인 삭제
- `hidden_at` + `hidden_reason` — 어드민 숨김(신고 처리 이력)
한 컬럼에 섞으면 "누가 왜 내렸나"를 사후에 답할 수 없다.

신고는 글·댓글을 한 테이블에서 받는다(`target_type`) — 두 테이블을 가리키므로 FK가 없고,
대상 존재 확인은 유스케이스가 한다. (대상, 신고자) 유니크로 반복 신고를 1건으로 접는다.
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "g3c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "g2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "game_community_posts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("epoch_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_tick", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hidden_reason", sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # 토론방은 항상 "이 종목의 최신 글"로 열린다
    op.create_index(
        "ix_game_community_posts_symbol_created",
        "game_community_posts",
        ["symbol", "created_at"],
    )
    op.create_index("ix_game_community_posts_user", "game_community_posts", ["user_id"])

    op.create_table(
        "game_community_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("epoch_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_tick", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hidden_reason", sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(["post_id"], ["game_community_posts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    # 조회는 항상 "이 글의 댓글 전부"로 들어간다
    op.create_index(
        "ix_game_community_comments_post",
        "game_community_comments",
        ["post_id", "created_at"],
    )

    op.create_table(
        "game_community_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        # post | comment — 두 테이블을 가리키므로 FK를 걸 수 없다
        sa.Column("target_type", sa.String(length=8), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("reporter_user_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["reporter_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        # 한 사람이 반복 신고로 검토 우선순위를 만들 수 없게 한다
        sa.UniqueConstraint(
            "target_type",
            "target_id",
            "reporter_user_id",
            name="uq_game_community_reports_target_reporter",
        ),
    )
    op.create_index(
        "ix_game_community_reports_target",
        "game_community_reports",
        ["target_type", "target_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_game_community_reports_target", table_name="game_community_reports")
    op.drop_table("game_community_reports")
    op.drop_index("ix_game_community_comments_post", table_name="game_community_comments")
    op.drop_table("game_community_comments")
    op.drop_index("ix_game_community_posts_user", table_name="game_community_posts")
    op.drop_index("ix_game_community_posts_symbol_created", table_name="game_community_posts")
    op.drop_table("game_community_posts")
