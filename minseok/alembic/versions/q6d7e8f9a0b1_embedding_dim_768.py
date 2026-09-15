"""임베딩 차원 1024(bge-m3) → 768(embeddinggemma) — 2026-09-15 임베딩 모델 교체

기존 벡터는 새 모델과 공간이 달라 쓸 수 없으므로 전부 NULL로 비운다(USING NULL).
재임베딩은 각 수집 경로의 미임베딩 백필(unembedded → set_embeddings)과
scripts/collect_disclosures.py --embed 가 채운다. 실측 소요 ≈ 뉴스 10.6만 건 1시간 + 공시 청크 10.1만 건 45분.

Revision ID: q6d7e8f9a0b1
Revises: p5c6d7e8f9a0
"""
from alembic import op

revision = "q6d7e8f9a0b1"
down_revision = "p5c6d7e8f9a0"
branch_labels = None
depends_on = None

_TABLES = ("news_articles", "disclosure_chunks", "inbound_mails", "market_news_articles")


def _retype(dim: int) -> None:
    for table in _TABLES:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector({dim}) USING NULL::vector({dim})"
        )


def upgrade() -> None:
    _retype(768)


def downgrade() -> None:
    _retype(1024)  # 벡터는 복구되지 않는다 — bge-m3로 재임베딩해야 한다
