"""하이브리드 검색(R2) — pg_trgm 확장 + news_articles.title trigram GIN 인덱스

키워드 채널(similarity(title, :q))용. 문자 3-gram이라 조사·띄어쓰기 변형에는 강하나
형태소 분석이 아니어서 의미 확장은 안 된다(R2 한계 명시). pg_trgm은 trusted 확장이라
DB owner 권한으로 생성 가능하다.

Revision ID: j9c0d1e2f3a4
Revises: i8b9c0d1e2f3
Create Date: 2026-08-23
"""
from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "j9c0d1e2f3a4"
down_revision: Union[str, Sequence[str], None] = "i8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index(
        "ix_news_articles_title_trgm",
        "news_articles",
        ["title"],
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )


def downgrade() -> None:
    # 확장은 지우지 않는다 — 다른 인덱스·세션이 쓰고 있을 수 있다(인덱스만 회수).
    op.drop_index("ix_news_articles_title_trgm", table_name="news_articles")
