"""검색 평가 러너(R1) — 골든셋 40질의를 실 코퍼스에 돌려 트레이스·pooling 후보를 만든다.

현행 검색(제목 bge-m3 임베딩 × pgvector 코사인 top-k)을 **프로덕션과 같은 유스케이스**로
호출한다. stock 질의는 news_articles(공유 DB, 코퍼스 횡단 ticker=None), market 질의는
market_news_articles(market 전용 DB)를 검색한다.

산출물(apps/chat/tests/eval/):
- retrieval_trace.jsonl — 케이스별 랭킹(문서 id) → 게이트(test_retrieval_gate.py)가 채점
- retrieval_pool.jsonl  — 케이스별 top-20 후보(제목·날짜·태그) = **사람 라벨링 시트**.
  TREC pooling: 이 후보에 사람이 0(무관)/1(관련)/2(정답급)을 매겨
  retrieval_golden.jsonl의 labels를 채운다. ⛔ 라벨링을 LLM에 시키지 않는다.

이 파일이 chat 스포크 밖(합성 루트 위상)에 있는 이유: stock·market의 구체 유스케이스를
함께 조립해야 하는데 chat/tests 안에서는 스포크 상호 독립 계약(import-linter)에 걸린다 —
main.py가 스포크들을 조립하는 것과 같은 자리다.

실행(백엔드 PC — ollama bge-m3 + 실 DB 필요, market DB는 MARKET_DATABASE_URL):
  docker run --rm --network host \
    -v /home/host/projects/com.redoceanmap:/work -w /work \
    -e PYTHONPATH=/work/minseok:/work/minseok/apps \
    --env-file /home/host/projects/com.redoceanmap/.env \
    minseok97/redoceanmap-backend:latest \
    python -m pytest minseok/tests/test_retrieval_runner.py \
      -q -p no:cacheprovider -m ollama -s
"""
from __future__ import annotations

import json

import pytest

from chat.tests.eval.retrieval import (
    RETRIEVAL_POOL_PATH,
    RETRIEVAL_TRACE_PATH,
    load_retrieval_cases,
)
from core.database import get_db, get_market_db
from market.adapter.outbound.ai.ollama_embedding_adapter import (
    OllamaEmbeddingAdapter as MarketEmbeddingAdapter,
)
from market.adapter.outbound.pg.market_news_pg_repository import MarketNewsPgRepository
from market.app.use_cases.market_news_interactor import MarketNewsInteractor
from stock.adapter.outbound.ai.ollama_embedding_adapter import (
    OllamaEmbeddingAdapter as StockEmbeddingAdapter,
)
from stock.adapter.outbound.pg.news_pg_repository import NewsPgRepository
from stock.app.use_cases.news_interactor import NewsInteractor

pytestmark = pytest.mark.ollama

# TREC pooling 깊이 — 코사인 top-20을 사람이 라벨한다(ROADMAP R1)
POOL_DEPTH = 20


async def _search(case, stock_uc: NewsInteractor, market_uc: MarketNewsInteractor):
    """카테고리에 맞는 코퍼스를 검색해 (문서 키, 라벨링 메타) 목록을 돌려준다."""
    if case.category == "stock":
        rows = await stock_uc.search(case.query, ticker=None, limit=POOL_DEPTH)
        return [
            (str(r.id), {
                "title": r.title, "tag": r.ticker or "종목 무관", "source": r.source,
                "published_at": f"{r.published_at:%Y-%m-%d}" if r.published_at else None,
            })
            for r in rows
        ]
    rows = await market_uc.search(case.query, limit=POOL_DEPTH)
    return [
        (str(r.id), {
            "title": r.title, "tag": r.area_tag, "source": r.source,
            "published_at": f"{r.published_at:%Y-%m-%d}" if r.published_at else None,
        })
        for r in rows
    ]


async def test_retrieval_runner():
    cases = load_retrieval_cases()
    traces: list[dict] = []
    pool: list[dict] = []

    # 프로바이더와 같은 조립 — DI 없이 세션 제너레이터를 직접 소비한다
    async for db in get_db():
        async for market_db in get_market_db():
            stock_uc = NewsInteractor(
                news=NewsPgRepository(session=db), embeddings=StockEmbeddingAdapter(),
            )
            market_uc = MarketNewsInteractor(
                news=MarketNewsPgRepository(session=market_db),
                embeddings=MarketEmbeddingAdapter(),
            )
            for case in cases:
                try:
                    hits = await _search(case, stock_uc, market_uc)
                    error = None if hits else "검색 결과 0건 — 임베딩 실패 또는 빈 코퍼스"
                except Exception as exc:  # 케이스 하나가 러너 전체를 깨지 않게
                    hits, error = [], f"{type(exc).__name__}: {exc}"
                traces.append({
                    "case_id": case.case_id,
                    "results": [doc for doc, _ in hits],
                    "error": error,
                })
                pool.append({
                    "case_id": case.case_id, "category": case.category, "query": case.query,
                    "candidates": [{"doc": doc, **meta} for doc, meta in hits],
                })
                print(f"[retrieval-runner] {case.case_id} {len(hits)}건"
                      f"{' — ' + error if error else ''}")

    RETRIEVAL_TRACE_PATH.write_text(
        "\n".join(json.dumps(t, ensure_ascii=False) for t in traces) + "\n", encoding="utf-8",
    )
    RETRIEVAL_POOL_PATH.write_text(
        "\n".join(json.dumps(p, ensure_ascii=False) for p in pool) + "\n", encoding="utf-8",
    )
    print(f"[retrieval-runner] 트레이스 {len(traces)}건 → {RETRIEVAL_TRACE_PATH}")
    print(f"[retrieval-runner] 라벨링 시트 → {RETRIEVAL_POOL_PATH}")
    failed = [t["case_id"] for t in traces if t["error"]]
    assert not failed, f"검색 실패 케이스: {failed}"
