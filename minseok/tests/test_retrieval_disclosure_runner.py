"""공시 청킹 평가 러너(R3) — 공시 골든셋 20질의를 전략별 청크 코퍼스에 돌린다.

선행: scripts/collect_disclosures.py 로 disclosure_chunks 적재 + --embed 임베딩 완료.
전략별(a 고정 토큰 대조군 / b 섹션 / c 표 인지) 코사인 top-20을 각각 트레이스로 남기고,
세 전략 합집합을 pooling 라벨링 시트로 만든다 — 사람이 0/1/2를 붙여
retrieval_golden_disclosure.jsonl의 labels를 채운다(⛔ LLM 라벨링 금지).

판정은 test_retrieval_chunking_report.py — (c)가 (a) 대비 표 질의(recall@5) +0.10 게이트.

실행(백엔드 PC — 실 DB + ollama bge-m3):
  docker run --rm --network host \
    -v /home/host/projects/com.redoceanmap:/work -w /work \
    -e PYTHONPATH=/work/minseok:/work/minseok/apps \
    --env-file /home/host/projects/com.redoceanmap/.env \
    minseok97/redoceanmap-backend:latest \
    python -m pytest minseok/tests/test_retrieval_disclosure_runner.py \
      -q -p no:cacheprovider -m ollama -s
"""
from __future__ import annotations

import json

import pytest

from chat.tests.eval.retrieval import (
    DISCLOSURE_STRATEGIES,
    RETRIEVAL_GOLDEN_DISCLOSURE_PATH,
    RETRIEVAL_POOL_DISCLOSURE_PATH,
    RETRIEVAL_TRACE_DISCLOSURE_PATHS,
    load_retrieval_cases,
)
from core.database import get_db
from core.llm.llm_orchestrator import llm_orchestrator
from stock.adapter.outbound.pg.disclosure_pg_repository import DisclosurePgRepository

pytestmark = pytest.mark.ollama

POOL_DEPTH = 20


async def test_retrieval_disclosure_runner():
    cases = load_retrieval_cases(RETRIEVAL_GOLDEN_DISCLOSURE_PATH)
    traces: dict[str, list[dict]] = {s: [] for s in DISCLOSURE_STRATEGIES}
    pool: list[dict] = []

    async for db in get_db():
        repo = DisclosurePgRepository(session=db)
        for case in cases:
            candidates: list[dict] = []
            seen: set[str] = set()
            try:
                embedding = await llm_orchestrator.embed(case.query)
                error = None
            except Exception as exc:
                embedding, error = None, f"{type(exc).__name__}: {exc}"
            for strategy in DISCLOSURE_STRATEGIES:
                hits = []
                if embedding is not None:
                    hits = await repo.search_similar(embedding, strategy, limit=POOL_DEPTH)
                strategy_error = error or (
                    None if hits else "검색 결과 0건 — 코퍼스 미적재 또는 미임베딩"
                )
                traces[strategy].append({
                    "case_id": case.case_id,
                    "results": [str(h.id) for h in hits],
                    "error": strategy_error,
                })
                for h in hits:
                    doc = str(h.id)
                    if doc in seen:
                        continue
                    seen.add(doc)
                    candidates.append({
                        "doc": doc, "strategy": h.strategy, "corp": h.corp_name,
                        "kind": h.kind, "section": h.section_path,
                        "content": h.content[:200],  # 라벨링 판독용 발췌
                    })
            pool.append({
                "case_id": case.case_id, "category": case.category, "query": case.query,
                "candidates": candidates,
            })
            print(f"[disclosure-runner] {case.case_id} pool {len(candidates)}건")

    for strategy, rows in traces.items():
        RETRIEVAL_TRACE_DISCLOSURE_PATHS[strategy].write_text(
            "\n".join(json.dumps(t, ensure_ascii=False) for t in rows) + "\n",
            encoding="utf-8",
        )
    RETRIEVAL_POOL_DISCLOSURE_PATH.write_text(
        "\n".join(json.dumps(p, ensure_ascii=False) for p in pool) + "\n", encoding="utf-8",
    )
    print(f"[disclosure-runner] 전략별 트레이스 3벌 + 라벨링 시트 → {RETRIEVAL_POOL_DISCLOSURE_PATH}")
    failed = [t["case_id"] for rows in traces.values() for t in rows if t["error"]]
    assert not failed, f"검색 실패 케이스: {sorted(set(failed))}"
