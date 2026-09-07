#!/usr/bin/env python3
"""collect_seoul_quarter.py — 상권 신규 분기 자동 적재(③-M5).

서울 열린데이터광장 OpenAPI를 폴링해 market DB에 없는 새 분기가 공개되면 받아서
기존 적재 경로로 넣는다. 서울시의 분기 공개 시점이 불규칙해 **주 1회 폴링**이 정책이다
(신규 없으면 no-op — 팩트별 확인 호출 몇 번이 전부).

동작:
  1. market DB에서 팩트별 max(year_quarter) 조회
  2. 그다음 분기부터 현재 분기까지 후보 분기를 API로 확인·수집
  3. API 필드 코드 → 한글 CSV 헤더로 변환해 연도별 CSV(기존 파일명 규칙·cp949)에
     병합 저장 — 같은 분기 행은 교체(재실행 멱등)
  4. `ingest_seoul_3nf.py --facts <팩트> --years <연도>` 서브프로세스로 적재
     (기존 멱등 INSERT·FK 필터 경로 재사용 — 적재 로직을 복제하지 않는다)

⚠ 분기 필터(`/{start}/{end}/{분기코드}/`)는 **서비스마다 지원이 갈린다**(2026-08-23 실측 —
가짜 분기 99999 대조): 매출·점포·유동·상권변화는 서버 필터 동작, 상주·직장·집객은 인자가
무시되고 전량이 온다. 무시되는 3종은 총량이 3.4만 건 수준이라 전량 페이징 후 클라이언트
분기 필터로 처리한다. 미공개 분기는 INFO-200("데이터 없음")이 **정상 응답**이다 — 오류 아님.

대상 팩트 7종: 매출·점포·유동·상주·직장·상권변화·집객시설.
소득소비·아파트는 실사 시점 API가 ERROR-500 — 제외(CSV 수동 경로 유지, 복구 시 확장).

시도 벤치마크 캐시·area_score는 최신 분기 키라 적재 후 자연 갱신된다(캐시 무효화 불요).

실행(백엔드 PC — market DB). 스케줄은 k8s/overlays/prod/cronjobs/collect-seoul-quarter.yaml(매주 수 05:30,
리포를 /work로 마운트해 체크아웃 코드를 실행):
  kubectl -n redocean create job --from=cronjob/collect-seoul-quarter collect-seoul-quarter-manual-$(date +%s)
  # 옵션이 필요하면 실행 중 파드에서(이미지 코드):
  kubectl -n redocean exec deploy/backend -- python scripts/collect_seoul_quarter.py [--probe] [--dry-run]

  --probe   : DB 없이 API 최신 분기 현황만 출력(로컬 점검용)
  --dry-run : 수집·CSV 저장까지 하고 적재(ingest)만 생략
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.request
from datetime import date
from json import loads
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))

from core.key.secret_manager import get_secret_manager  # noqa: E402
from market.adapter.outbound.csv.column_maps import (  # noqa: E402
    COMMERCIAL_CHANGE_API_COLUMN_MAP,
    COMMERCIAL_CHANGE_COLUMN_MAP,
    ESTIMATED_SALES_API_COLUMN_MAP,
    ESTIMATED_SALES_COLUMN_MAP,
    FACILITY_COLUMN_MAP,
    FLOATING_POPULATION_API_COLUMN_MAP,
    FLOATING_POPULATION_COLUMN_MAP,
    RESIDENT_POPULATION_API_COLUMN_MAP,
    RESIDENT_POPULATION_COLUMN_MAP,
    STORE_API_COLUMN_MAP,
    STORE_COLUMN_MAP,
    WORKING_POPULATION_API_COLUMN_MAP,
    WORKING_POPULATION_COLUMN_MAP,
)

_secrets = get_secret_manager()
API_KEY = _secrets.get("SEOUL_OPENDATA_API_KEY")
DATA = ROOT / "data" / "raw" / "seoul"
ENC = "cp949"  # 기존 상권 CSV와 동일 — ingest가 이 인코딩으로 읽는다
PAGE = 1000    # OpenAPI 1회 최대 건수

# (팩트 테이블명, API 서비스, API 맵, CSV 맵, CSV 파일 라벨, 서버 분기 필터 지원)
# CSV 맵이 곧 파일 헤더다 — facility는 CSV도 API 코드 헤더라 두 맵이 같다(fetch 선례).
FACTS = [
    ("estimated_sales", "VwsmTrdarSelngQq",
     ESTIMATED_SALES_API_COLUMN_MAP, ESTIMATED_SALES_COLUMN_MAP, "추정매출-상권", True),
    ("store", "VwsmTrdarStorQq",
     STORE_API_COLUMN_MAP, STORE_COLUMN_MAP, "점포-상권", True),
    ("floating_population", "VwsmTrdarFlpopQq",
     FLOATING_POPULATION_API_COLUMN_MAP, FLOATING_POPULATION_COLUMN_MAP, "길단위인구-상권", True),
    ("resident_population", "VwsmTrdarRepopQq",
     RESIDENT_POPULATION_API_COLUMN_MAP, RESIDENT_POPULATION_COLUMN_MAP, "상주인구-상권", False),
    ("working_population", "VwsmTrdarWrcPopltnQq",
     WORKING_POPULATION_API_COLUMN_MAP, WORKING_POPULATION_COLUMN_MAP, "직장인구-상권", False),
    ("commercial_change", "VwsmTrdarIxQq",
     COMMERCIAL_CHANGE_API_COLUMN_MAP, COMMERCIAL_CHANGE_COLUMN_MAP, "상권변화지표-상권", True),
    ("facility", "VwsmTrdarFcltyQq",
     FACILITY_COLUMN_MAP, FACILITY_COLUMN_MAP, "집객시설-상권", False),
]

_EMPTY = {"list_total_count": 0, "row": []}


def _fetch(service: str, start: int, end: int, quarter: int | None = None) -> dict:
    suffix = f"{quarter}/" if quarter else ""
    url = f"http://openapi.seoul.go.kr:8088/{API_KEY}/json/{service}/{start}/{end}/{suffix}"
    for attempt in (1, 2, 3):  # 공공 API는 간헐적으로 끊긴다 — 짧게 재시도(fetch 선례)
        try:
            with urllib.request.urlopen(url, timeout=60) as res:
                body = loads(res.read().decode("utf-8"))
            if service in body:
                return body[service]
            result = body.get("RESULT", {})
            if result.get("CODE") == "INFO-200":
                return _EMPTY  # "해당하는 데이터가 없습니다" — 미공개 분기의 정상 응답
            raise RuntimeError(str(result or body)[:200])
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 * attempt)
    raise RuntimeError("unreachable")


def quarter_count(service: str, quarter: int) -> int:
    """해당 분기의 API 보유 건수(서버 필터 지원 서비스 전용) — 0이면 아직 미공개."""
    try:
        return int(_fetch(service, 1, 1, quarter)["list_total_count"])
    except Exception as exc:
        print(f"    확인 실패({exc}) — 이번 실행에서는 건너뜀")
        return 0


def _paged(service: str, total: int, quarter: int | None) -> list[dict]:
    rows: list[dict] = []
    for start in range(1, total + 1, PAGE):
        rows.extend(_fetch(service, start, min(start + PAGE - 1, total), quarter)["row"])
    return rows


def fetch_quarter(service: str, quarter: int) -> list[dict]:
    """서버 분기 필터 지원 서비스 — 해당 분기만 페이징."""
    return _paged(service, quarter_count(service, quarter), quarter)


def fetch_all(service: str) -> list[dict]:
    """서버 필터가 무시되는 서비스 — 전량 페이징(총 3.4만 건 수준, 주 1회 감당)."""
    total = int(_fetch(service, 1, 1)["list_total_count"])
    return _paged(service, total, None)


def current_quarter() -> int:
    today = date.today()
    return today.year * 10 + (today.month - 1) // 3 + 1


def next_quarters(latest: int) -> list[int]:
    """DB 최신 분기 다음부터 현재 분기까지의 후보 목록."""
    year, q = latest // 10, latest % 10
    out: list[int] = []
    while True:
        q += 1
        if q > 4:
            year, q = year + 1, 1
        candidate = year * 10 + q
        if candidate > current_quarter():
            return out
        out.append(candidate)


def db_latest_quarters() -> dict[str, int]:
    """market DB의 팩트별 max(year_quarter) — backtest_area_score와 같은 동기 엔진 경로."""
    from sqlalchemy import create_engine, text
    engine = create_engine(
        (_secrets.get("MARKET_DATABASE_URL") or _secrets.require("DATABASE_URL"))
        .replace("postgresql://", "postgresql+psycopg://")
        .replace("postgresql+asyncpg://", "postgresql+psycopg://")
    )
    out: dict[str, int] = {}
    with engine.connect() as conn:
        for fact, *_ in FACTS:
            value = conn.execute(text(f"SELECT max(year_quarter) FROM {fact}")).scalar()
            out[fact] = int(value) if value else 0
    return out


def _group_by_quarter(rows: list[dict], wanted: list[int]) -> dict[int, list[dict]]:
    """전량 응답을 분기별로 갈라 후보 분기만 남긴다(서버 필터 미지원 서비스용)."""
    wanted_set = set(wanted)
    grouped: dict[int, list[dict]] = {}
    for row in rows:
        try:
            quarter = int(row.get("STDR_YYQU_CD", 0))
        except (TypeError, ValueError):
            continue
        if quarter in wanted_set:
            grouped.setdefault(quarter, []).append(row)
    return grouped


def merge_into_csv(rows: list[dict], api_map: dict, csv_map: dict, label: str,
                   quarter: int) -> Path:
    """API 행을 기존 CSV 헤더로 변환해 연도별 파일에 병합 — 같은 분기 행은 교체(멱등)."""
    orm_to_header = {orm: header for header, orm in csv_map.items()}
    frame = pd.DataFrame(rows).rename(columns=api_map)
    frame = frame[[c for c in frame.columns if c in orm_to_header]].rename(columns=orm_to_header)
    quarter_header = orm_to_header["year_quarter"]

    path = DATA / f"서울시 상권분석서비스({label})_{quarter // 10}년.csv"
    if path.exists():
        existing = pd.read_csv(path, encoding=ENC)
        existing = existing[existing[quarter_header].astype(int) != quarter]
        frame = pd.concat([existing, frame], ignore_index=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding=ENC)
    return path


def run_ingest(facts: set[str], years: set[int]) -> None:
    cmd = [
        sys.executable, str(ROOT / "scripts" / "ingest_seoul_3nf.py"),
        "--facts", ",".join(sorted(facts)),
        "--years", ",".join(str(y) for y in sorted(years)),
    ]
    print(f"[quarter] 적재: {' '.join(cmd[1:])}")
    subprocess.run(cmd, check=True)


def probe() -> None:
    """DB 없이 API 현황만 — 팩트별 최근 두 분기의 보유 여부."""
    quarter = current_quarter()
    previous = quarter - 1 if quarter % 10 > 1 else (quarter // 10 - 1) * 10 + 4
    candidates = [previous, quarter]
    for fact, service, *_, server_filter in FACTS:
        if server_filter:
            counts = {q: quarter_count(service, q) for q in candidates}
        else:
            grouped = _group_by_quarter(fetch_all(service), candidates)
            counts = {q: len(grouped.get(q, [])) for q in candidates}
        print(f"[probe] {fact:22s} {counts}"
              f"{'' if server_filter else '  (서버 필터 미지원 — 전량 후 분기 분해)'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="상권 신규 분기 자동 적재")
    parser.add_argument("--probe", action="store_true", help="DB 없이 API 현황만 확인")
    parser.add_argument("--dry-run", action="store_true", help="수집·CSV 저장까지, 적재 생략")
    args = parser.parse_args()

    if not API_KEY:
        sys.exit("SEOUL_OPENDATA_API_KEY 미설정")
    if args.probe:
        probe()
        return

    latest = db_latest_quarters()
    ingested_facts: set[str] = set()
    ingested_years: set[int] = set()
    for fact, service, api_map, csv_map, label, server_filter in FACTS:
        candidates = next_quarters(latest[fact]) if latest[fact] else []
        if not candidates:
            print(f"[quarter] {fact}: DB 최신 {latest[fact]} — 신규 후보 없음")
            continue
        if server_filter:
            quarter_rows = {
                q: fetch_quarter(service, q)
                for q in candidates if quarter_count(service, q) > 0
            }
        else:
            quarter_rows = _group_by_quarter(fetch_all(service), candidates)
        for quarter in candidates:
            rows = quarter_rows.get(quarter, [])
            if not rows:
                print(f"[quarter] {fact}: {quarter} 미공개")
                continue
            path = merge_into_csv(rows, api_map, csv_map, label, quarter)
            print(f"[quarter] {fact}: {quarter} 수집 {len(rows):,}건 → {path.name}")
            ingested_facts.add(fact)
            ingested_years.add(quarter // 10)

    if not ingested_facts:
        print("[quarter] 신규 분기 없음 — 종료")
        return
    if args.dry_run:
        print("[quarter] dry-run — 적재 생략")
        return
    run_ingest(ingested_facts, ingested_years)


if __name__ == "__main__":
    main()
