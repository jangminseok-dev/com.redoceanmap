"""검색 평가 러너(R1·R2) — 골든셋 40질의를 실 코퍼스에 돌려 트레이스·pooling 후보를 만든다.

두 시스템을 나란히 실행한다:
- **현행**(R1 baseline 대상): 제목 임베딩(EMBED_MODEL — 2026-09-15부터 embeddinggemma) × pgvector 코사인 top-k —
  **프로덕션과 같은 유스케이스**로 호출한다.
- **하이브리드**(R2 실험): 벡터 + trigram 키워드 채널 RRF 결합 —
  리포지토리의 search_hybrid(아직 프로덕션 경로 아님)를 직접 호출한다.
  선행: pg_trgm 마이그레이션(공유 DB j9c0d1e2f3a4 · market DB d8e9f0a1b2c3).

stock 질의는 news_articles(공유 DB, 코퍼스 횡단 ticker=None), market 질의는
market_news_articles(market 전용 DB)를 검색한다.

산출물(apps/chat/tests/eval/):
- retrieval_trace.jsonl        — 현행 랭킹 → 게이트(test_retrieval_gate.py)가 채점
- retrieval_trace_hybrid.jsonl — 하이브리드 랭킹 → 비교 리포트(test_retrieval_hybrid_report.py)
- retrieval_pool.jsonl         — **두 시스템 합집합** top 후보 = 사람 라벨링 시트(TREC pooling).
  이 후보에 사람이 0(무관)/1(관련)/2(정답급)를 매겨 retrieval_golden.jsonl의 labels를
  채운다. ⛔ 라벨링을 LLM에 시키지 않는다.

이 파일이 chat 스포크 밖(합성 루트 위상)에 있는 이유: stock·market의 구체 유스케이스를
함께 조립해야 하는데 chat/tests 안에서는 스포크 상호 독립 계약(import-linter)에 걸린다 —
main.py가 스포크들을 조립하는 것과 같은 자리다.

실행(백엔드 PC — ollama 임베딩 모델 + 실 DB 필요, market DB는 MARKET_DATABASE_URL):
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
    RETRIEVAL_TRACE_HYBRID_PATH,
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

# TREC pooling 깊이 — 시스템별 top-20을 뽑고 합집합을 사람이 라벨한다(ROADMAP R1·R2)
POOL_DEPTH = 20


def _stock_meta(r) -> dict:
    return {
        "title": r.title, "tag": r.ticker or "종목 무관", "source": r.source,
        "published_at": f"{r.published_at:%Y-%m-%d}" if r.published_at else None,
    }


def _market_meta(r) -> dict:
    return {
        "title": r.title, "tag": r.area_tag, "source": r.source,
        "published_at": f"{r.published_at:%Y-%m-%d}" if r.published_at else None,
    }


async def test_retrieval_runner():
    cases = load_retrieval_cases()
    traces: list[dict] = []
    hybrid_traces: list[dict] = []
    pool: list[dict] = []

    # 프로바이더와 같은 조립 — DI 없이 세션 제너레이터를 직접 소비한다
    async for db in get_db():
        async for market_db in get_market_db():
            stock_repo = NewsPgRepository(session=db)
            market_repo = MarketNewsPgRepository(session=market_db)
            stock_embed = StockEmbeddingAdapter()
            market_embed = MarketEmbeddingAdapter()
            stock_uc = NewsInteractor(news=stock_repo, embeddings=stock_embed)
            market_uc = MarketNewsInteractor(news=market_repo, embeddings=market_embed)

            for case in cases:
                try:
                    if case.category == "stock":
                        # 현행 = 프로덕션 유스케이스 경로 그대로(내부에서 임베딩)
                        cosine = await stock_uc.search(case.query, ticker=None, limit=POOL_DEPTH)
                        hybrid = await stock_repo.search_hybrid(
                            await stock_embed.embed(case.query), case.query,
                            ticker=None, limit=POOL_DEPTH,
                        )
                        meta = _stock_meta
                    else:
                        cosine = await market_uc.search(case.query, limit=POOL_DEPTH)
                        hybrid = await market_repo.search_hybrid(
                            await market_embed.embed(case.query), case.query, limit=POOL_DEPTH,
                        )
                        meta = _market_meta
                    error = None if cosine else "검색 결과 0건 — 임베딩 실패 또는 빈 코퍼스"
                except Exception as exc:  # 케이스 하나가 러너 전체를 깨지 않게
                    cosine, hybrid, error, meta = [], [], f"{type(exc).__name__}: {exc}", None

                traces.append({
                    "case_id": case.case_id,
                    "results": [str(r.id) for r in cosine],
                    "error": error,
                })
                hybrid_traces.append({
                    "case_id": case.case_id,
                    "results": [str(r.id) for r in hybrid],
                    "error": error,
                })
                # pooling 후보 = 두 시스템 합집합(현행 순서 우선, 하이브리드 신규는 뒤에)
                candidates: list[dict] = []
                seen: set[str] = set()
                for r in list(cosine) + list(hybrid):
                    doc = str(r.id)
                    if doc in seen:
                        continue
                    seen.add(doc)
                    candidates.append({"doc": doc, **meta(r)})
                pool.append({
                    "case_id": case.case_id, "category": case.category, "query": case.query,
                    "candidates": candidates,
                })
                print(f"[retrieval-runner] {case.case_id} 현행 {len(cosine)}건"
                      f" · 하이브리드 {len(hybrid)}건 · pool {len(candidates)}건"
                      f"{' — ' + error if error else ''}")

    RETRIEVAL_TRACE_PATH.write_text(
        "\n".join(json.dumps(t, ensure_ascii=False) for t in traces) + "\n", encoding="utf-8",
    )
    RETRIEVAL_TRACE_HYBRID_PATH.write_text(
        "\n".join(json.dumps(t, ensure_ascii=False) for t in hybrid_traces) + "\n",
        encoding="utf-8",
    )
    RETRIEVAL_POOL_PATH.write_text(
        "\n".join(json.dumps(p, ensure_ascii=False) for p in pool) + "\n", encoding="utf-8",
    )
    print(f"[retrieval-runner] 현행 트레이스 {len(traces)}건 → {RETRIEVAL_TRACE_PATH}")
    print(f"[retrieval-runner] 하이브리드 트레이스 → {RETRIEVAL_TRACE_HYBRID_PATH}")
    print(f"[retrieval-runner] 라벨링 시트(합집합) → {RETRIEVAL_POOL_PATH}")
    failed = [t["case_id"] for t in traces if t["error"]]
    assert not failed, f"검색 실패 케이스: {failed}"
