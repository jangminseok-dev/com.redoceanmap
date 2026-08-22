"""하이브리드 검색(R2) — pg_trgm 확장 + market_news_articles.title trigram GIN 인덱스

키워드 채널(similarity(title, :q))용 — 공유 DB의 j9c0d1e2f3a4와 같은 목적(체인 독립).
문자 3-gram이라 형태소 분석이 아니다(R2 한계 명시). pg_trgm은 trusted 확장.

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
"""
from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index(
        "ix_market_news_articles_title_trgm",
        "market_news_articles",
        ["title"],
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )


def downgrade() -> None:
    # 확장은 지우지 않는다 — 다른 인덱스·세션이 쓰고 있을 수 있다(인덱스만 회수).
    op.drop_index("ix_market_news_articles_title_trgm", table_name="market_news_articles")
