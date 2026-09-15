"""market_news_articles 임베딩 차원 1024(bge-m3) → 768(embeddinggemma) — 2026-09-15 임베딩 모델 교체

공유 DB의 q6d7e8f9a0b1과 짝. 기존 벡터는 NULL로 비우고 상권 뉴스 수집(01:30 cron)의
미임베딩 백필이 다시 채운다(1,232건 — 수 분).

Revision ID: e9a1b2c3d4e5
Revises: d8f0a1b2c3d4
"""
from alembic import op

revision = "e9a1b2c3d4e5"
down_revision = "d8f0a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE market_news_articles ALTER COLUMN embedding TYPE vector(768) USING NULL::vector(768)")


def downgrade() -> None:
    op.execute("ALTER TABLE market_news_articles ALTER COLUMN embedding TYPE vector(1024) USING NULL::vector(1024)")
