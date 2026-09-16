"""한국부동산원 R-ONE 상가 임대동향 수집 — 서울 상권·권역·시 임대료(원/㎡·월)·공실률(%) → rent_benchmarks.

창업 재무 엔진(FINANCE_ENGINE_2026-09-16)의 월세 기본값 원천. 표는 2024년 3분기~ 빈티지만 쓴다
(옛 빈티지는 불연속이라 지수화 소비처가 생길 때까지 미적재). 서울 64 CLS(시 1·권역 4·상권 59) × 분기.

멱등 규칙: (building_type, year_quarter, cls_id) upsert — 재실행 안전.

실행 (백엔드 이미지 파드 — 호스트 cron venv에는 sqlalchemy가 없다):
    kubectl -n redocean exec deploy/backend -- python scripts/collect_rone_rent.py            # 전 분기
    ... python scripts/collect_rone_rent.py --dry-run                                         # 적재 없이 집계만

스케줄(분기 첫 달 10일 05:00 — R-ONE 공표는 분기 종료 후 약 1개월):
    infra/k8s/overlays/prod/cronjobs/collect-rone-rent.yaml
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))
from core.key.secret_manager import get_secret_manager  # noqa: E402

_secrets = get_secret_manager()

API_URL = "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"
PAGE_SIZE = 1000
# 건물유형 → (임대료 표, 공실률 표) — 2024년 3분기~ 빈티지(2026-09-16 SttsApiTbl 실측)
TABLES = {
    "small": ("T248223134698125", "T241833134686576"),
    "medium_large": ("T244363134858603", "T249633134845544"),
    "aggregate": ("T244913134948657", "T243283134931290"),
}


def market_url() -> str:
    url = _secrets.get("MARKET_DATABASE_URL") or _secrets.require("DATABASE_URL")
    return url.replace("postgresql://", "postgresql+psycopg://")


def parse_quarter(wrttime: str) -> int:
    """R-ONE `WRTTIME_IDTFR_ID` "202403"(연+0+분기) → 20243."""
    return int(wrttime[:4]) * 10 + int(wrttime[5])


def fetch_table(statbl_id: str) -> list[dict]:
    key = _secrets.require("RONE_API_KEY")
    rows: list[dict] = []
    page = 1
    while True:
        url = (f"{API_URL}?STATBL_ID={statbl_id}&DTACYCLE_CD=QY&KEY={key}&Type=json"
               f"&pIndex={page}&pSize={PAGE_SIZE}")
        with urlopen(url, timeout=60) as res:
            body = json.loads(res.read().decode("utf-8"))
        blocks = body.get("SttsApiTblData", [])
        head = next((b["head"] for b in blocks if "head" in b), [])
        result = next((h["RESULT"] for h in head if "RESULT" in h), {})
        if result.get("CODE") not in ("INFO-000", None):
            raise RuntimeError(f"{statbl_id}: {result}")
        page_rows = next((b["row"] for b in blocks if "row" in b), [])
        rows.extend(page_rows)
        total = next((h["list_total_count"] for h in head if "list_total_count" in h), 0)
        if page * PAGE_SIZE >= total or not page_rows:
            return rows
        page += 1


def merge_rows(building_type: str, rent_rows: list[dict], vacancy_rows: list[dict]) -> list[dict]:
    """서울 행만 남기고 임대료·공실률을 (분기, CLS)로 병합. 임대료 천원/㎡ → 원/㎡."""
    merged: dict[tuple[int, str], dict] = {}
    for r in rent_rows:
        fullnm = str(r.get("CLS_FULLNM", ""))
        if not fullnm.startswith("서울"):
            continue
        parts = fullnm.split(">")
        key = (parse_quarter(r["WRTTIME_IDTFR_ID"]), str(r["CLS_ID"]))
        merged[key] = {
            "building_type": building_type,
            "year_quarter": key[0],
            "cls_id": key[1],
            "cls_fullnm": fullnm,
            "level": len(parts) - 1,
            "region_name": parts[-1],
            "rent_per_sqm_krw": int(round(float(r["DTA_VAL"]) * 1000)),
            "vacancy_rate": None,
        }
    for r in vacancy_rows:
        key = (parse_quarter(r["WRTTIME_IDTFR_ID"]), str(r["CLS_ID"]))
        if key in merged:
            merged[key]["vacancy_rate"] = round(float(r["DTA_VAL"]), 2)
    return list(merged.values())


def upsert(conn, rows: list[dict]) -> None:
    conn.execute(text(
        "INSERT INTO rent_benchmarks (building_type, year_quarter, cls_id, cls_fullnm, level, "
        "region_name, rent_per_sqm_krw, vacancy_rate) "
        "VALUES (:building_type, :year_quarter, :cls_id, :cls_fullnm, :level, :region_name, "
        ":rent_per_sqm_krw, :vacancy_rate) "
        "ON CONFLICT (building_type, year_quarter, cls_id) DO UPDATE SET "
        "cls_fullnm = EXCLUDED.cls_fullnm, level = EXCLUDED.level, region_name = EXCLUDED.region_name, "
        "rent_per_sqm_krw = EXCLUDED.rent_per_sqm_krw, "
        "vacancy_rate = COALESCE(EXCLUDED.vacancy_rate, rent_benchmarks.vacancy_rate), "
        "collected_at = now()"
    ), rows)


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] R-ONE 수집 시작 — 건물유형 {len(TABLES)}종", flush=True)
    engine = None if dry_run else create_engine(market_url())
    total = failures = 0
    for building_type, (rent_id, vacancy_id) in TABLES.items():
        try:
            rows = merge_rows(building_type, fetch_table(rent_id), fetch_table(vacancy_id))
        except Exception as e:
            print(f"  [경고] {building_type} 실패({e}) — 계속", flush=True)
            failures += 1
            continue
        quarters = sorted({r["year_quarter"] for r in rows})
        print(f"{building_type}: {len(rows)}행 (분기 {quarters[:1]}~{quarters[-1:]})", flush=True)
        total += len(rows)
        if not dry_run and rows:
            with engine.begin() as conn:
                upsert(conn, rows)
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 합계 {total}행"
          + (" (dry-run — 적재 생략)" if dry_run else "")
          + (f" / 실패 {failures}종" if failures else ""), flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
