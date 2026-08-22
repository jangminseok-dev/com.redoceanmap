#!/usr/bin/env python3
"""collect_disclosures.py — R3 청킹 실험 코퍼스: DART 사업보고서 → 3전략 청킹 적재.

한국 10사 × 최신 사업보고서 1건을 공시서류원본파일 API로 받아 파싱하고,
전략별(a 고정 512자 / b 섹션 / c 표 인지)로 청킹해 disclosure_chunks에 적재한다.
(rcept_no, strategy) 단위 교체라 재실행이 멱등이다. `--embed`는 미임베딩 청크를
bge-m3(ollama)로 배치 임베딩한다(실패분은 재실행이 자연 재시도).

일회성 연구 배치 — cron 등록하지 않는다(사업보고서는 연 1회, 실험 코퍼스는 동결이 원칙).

실행(백엔드 PC — 실 DB, --embed는 ollama도 필요):
  docker run --rm --network host \
    -v /home/host/projects/com.redoceanmap:/work -w /work \
    -e PYTHONPATH=/work/minseok:/work/minseok/apps \
    --env-file /home/host/projects/com.redoceanmap/.env \
    minseok97/redoceanmap-backend:latest \
    python minseok/scripts/collect_disclosures.py [--embed] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import io
import sys
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))
sys.path.insert(0, str(ROOT / "scripts"))

from core.key.secret_manager import get_secret_manager  # noqa: E402
from collect_fundamentals import load_corp_codes  # noqa: E402 — corp 코드 30일 캐시 재사용

_secrets = get_secret_manager()
DART_API_KEY = _secrets.get("DART_API_KEY")
DART_URL = "https://opendart.fss.or.kr/api"

# 한국 10사 — 워치리스트 한국 고정 2사(삼성전자·SK하이닉스) + 시총 상위·업종 다양성.
# 실험 코퍼스 선정 기준: 표가 많은 제조·바이오·금융·플랫폼이 섞이게.
CORPS: dict[str, str] = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "373220": "LG에너지솔루션",
    "207940": "삼성바이오로직스",
    "005380": "현대차",
    "000270": "기아",
    "068270": "셀트리온",
    "035420": "NAVER",
    "005490": "POSCO홀딩스",
    "105560": "KB금융",
}

EMBED_BATCH = 100


def latest_annual_rcept(corp_code: str) -> str | None:
    """최신 사업보고서(A001) 접수번호 — 없으면 None."""
    res = requests.get(f"{DART_URL}/list.json", params={
        "crtfc_key": DART_API_KEY, "corp_code": corp_code,
        "pblntf_detail_ty": "A001", "bgn_de": "20230101", "end_de": "20991231",
        "page_count": "5",
    }, timeout=30)
    res.raise_for_status()
    body = res.json()
    if body.get("status") != "000":
        return None
    # 최신순 목록에서 정정 포함 첫 '사업보고서'
    for row in body.get("list", []):
        if "사업보고서" in row.get("report_nm", ""):
            return row["rcept_no"]
    return None


def download_document(rcept_no: str) -> str:
    """공시서류원본파일 ZIP → 본문 XML 텍스트({rcept_no}.xml — 첨부 xml은 제외)."""
    res = requests.get(f"{DART_URL}/document.xml", params={
        "crtfc_key": DART_API_KEY, "rcept_no": rcept_no,
    }, timeout=120)
    res.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        name = f"{rcept_no}.xml"
        if name not in zf.namelist():  # 방어 — 없으면 가장 큰 xml
            name = max(zf.infolist(), key=lambda i: i.file_size).filename
        return zf.read(name).decode("utf-8", errors="replace")


async def ingest(dry_run: bool) -> None:
    from core.database import get_db
    from stock.adapter.outbound.dart.disclosure_parser import parse_document
    from stock.adapter.outbound.pg.disclosure_pg_repository import DisclosurePgRepository
    from stock.domain.services.disclosure_chunker import STRATEGIES

    corp_codes = load_corp_codes()
    async for db in get_db():
        repo = DisclosurePgRepository(session=db)
        for stock_code, name in CORPS.items():
            corp_code = corp_codes.get(stock_code)
            if not corp_code:
                print(f"[disclosure] {name}({stock_code}) corp_code 없음 — 건너뜀")
                continue
            rcept_no = latest_annual_rcept(corp_code)
            if not rcept_no:
                print(f"[disclosure] {name} 사업보고서 없음 — 건너뜀")
                continue
            elements = parse_document(download_document(rcept_no))
            tables = sum(1 for e in elements if e.kind == "table")
            print(f"[disclosure] {name} {rcept_no}: 요소 {len(elements)}개(표 {tables})")
            for strategy, chunk_fn in STRATEGIES.items():
                chunks = chunk_fn(elements)
                if dry_run:
                    print(f"  - 전략 {strategy}: 청크 {len(chunks)}개 (dry-run — 적재 생략)")
                    continue
                saved = await repo.replace_chunks(corp_code, name, rcept_no, strategy, chunks)
                print(f"  - 전략 {strategy}: 청크 {saved}개 적재")


async def embed() -> None:
    from core.database import get_db
    from core.llm.llm_orchestrator import llm_orchestrator
    from stock.adapter.outbound.pg.disclosure_pg_repository import DisclosurePgRepository
    from stock.domain.services.disclosure_chunker import STRATEGIES

    async for db in get_db():
        repo = DisclosurePgRepository(session=db)
        for strategy in STRATEGIES:
            done = 0
            while True:
                batch = await repo.unembedded(strategy, limit=EMBED_BATCH)
                if not batch:
                    break
                vectors = await llm_orchestrator.embed_many([c.content for c in batch])
                for chunk, vector in zip(batch, vectors):
                    chunk.embedding = vector
                await repo.commit()
                done += len(batch)
                print(f"[disclosure] 전략 {strategy}: 임베딩 {done}개 누적")
            print(f"[disclosure] 전략 {strategy}: 임베딩 완료(신규 {done}개)")


def main() -> None:
    parser = argparse.ArgumentParser(description="R3 공시 청킹 코퍼스 수집·임베딩")
    parser.add_argument("--embed", action="store_true", help="미임베딩 청크 배치 임베딩")
    parser.add_argument("--dry-run", action="store_true", help="적재 없이 청크 수만 보고")
    args = parser.parse_args()
    if args.embed:
        asyncio.run(embed())
    else:
        asyncio.run(ingest(args.dry_run))


if __name__ == "__main__":
    main()
