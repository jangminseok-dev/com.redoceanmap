"""한국부동산원 R-ONE 상가 임대동향 수집 — 서울 상권·권역·시 임대료(원/㎡·월)·공실률(%)·수익률(소득·자본·투자, 분기 %)
→ rent_benchmarks, 서울 업종 대분류별 상가권리금(연간) → key_money_benchmarks.

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
# 건물유형 → (임대료 표, 공실률 표, 수익률 표) — 2024년 3분기~ 빈티지(2026-09-16·17 SttsApiTbl 실측)
TABLES = {
    "small": ("T248223134698125", "T241833134686576", "T246253134913401"),
    "medium_large": ("T244363134858603", "T249633134845544", "T242083134887473"),
    "aggregate": ("T244913134948657", "T243283134931290", "T246393134978815"),
}
# 시도별/업종별 상가권리금(연간, 2022년~) — 서울 × 업종 대분류
KEY_MONEY_TABLE = "A_2024_00445"
_RETURN_ITEMS = {"소득수익률": "income_return", "자본수익률": "capital_return", "투자수익률": "investment_return"}
_KEY_MONEY_ITEMS = {"권리금 유 비율": "key_money_ratio", "권리금 수준_평균": "avg_krw",
                    "권리금 수준_중위수": "median_krw", "권리금 수준_㎡당 평균": "per_sqm_avg_krw"}


def market_url() -> str:
    url = _secrets.get("MARKET_DATABASE_URL") or _secrets.require("DATABASE_URL")
    return url.replace("postgresql://", "postgresql+psycopg://")


def parse_quarter(wrttime: str) -> int:
    """R-ONE `WRTTIME_IDTFR_ID` "202403"(연+0+분기) → 20243."""
    return int(wrttime[:4]) * 10 + int(wrttime[5])


def fetch_table(statbl_id: str, cycle: str = "QY") -> list[dict]:
    key = _secrets.require("RONE_API_KEY")
    rows: list[dict] = []
    page = 1
    while True:
        url = (f"{API_URL}?STATBL_ID={statbl_id}&DTACYCLE_CD={cycle}&KEY={key}&Type=json"
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


def merge_rows(building_type: str, rent_rows: list[dict], vacancy_rows: list[dict],
               return_rows: list[dict] = ()) -> list[dict]:
    """서울 행만 남기고 임대료·공실률·수익률(소득·자본·투자)을 (분기, CLS)로 병합. 임대료 천원/㎡ → 원/㎡."""
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
            "vacancy_rate": None, "income_return": None, "capital_return": None, "investment_return": None,
        }
    for r in vacancy_rows:
        key = (parse_quarter(r["WRTTIME_IDTFR_ID"]), str(r["CLS_ID"]))
        if key in merged:
            merged[key]["vacancy_rate"] = round(float(r["DTA_VAL"]), 2)
    for r in return_rows:
        key = (parse_quarter(r["WRTTIME_IDTFR_ID"]), str(r["CLS_ID"]))
        column = _RETURN_ITEMS.get(str(r.get("ITM_NM", "")).strip())
        if key in merged and column and r.get("DTA_VAL") not in (None, ""):
            merged[key][column] = round(float(r["DTA_VAL"]), 3)
    return list(merged.values())


def key_money_rows(raw: list[dict]) -> list[dict]:
    """서울 × 업종 대분류 × 연도로 권리금 4항목을 모은다. 만원 → 원, 업종명 공백 정리("전체 " → "전체")."""
    merged: dict[tuple[int, str], dict] = {}
    for r in raw:
        if str(r.get("GRP_NM", "")).strip() != "서울":
            continue
        column = _KEY_MONEY_ITEMS.get(str(r.get("ITM_NM", "")).strip())
        if column is None or r.get("DTA_VAL") in (None, ""):
            continue
        group = " ".join(str(r["CLS_NM"]).split())
        key = (int(r["WRTTIME_IDTFR_ID"]), group)
        row = merged.setdefault(key, {"year": key[0], "region_name": "서울", "industry_group": group,
                                      "key_money_ratio": None, "avg_krw": None, "median_krw": None,
                                      "per_sqm_avg_krw": None})
        value = float(r["DTA_VAL"])
        row[column] = round(value, 1) if column == "key_money_ratio" else int(round(value * 10_000))
    return list(merged.values())


def upsert(conn, rows: list[dict]) -> None:
    conn.execute(text(
        "INSERT INTO rent_benchmarks (building_type, year_quarter, cls_id, cls_fullnm, level, "
        "region_name, rent_per_sqm_krw, vacancy_rate, income_return, capital_return, investment_return) "
        "VALUES (:building_type, :year_quarter, :cls_id, :cls_fullnm, :level, :region_name, "
        ":rent_per_sqm_krw, :vacancy_rate, :income_return, :capital_return, :investment_return) "
        "ON CONFLICT (building_type, year_quarter, cls_id) DO UPDATE SET "
        "cls_fullnm = EXCLUDED.cls_fullnm, level = EXCLUDED.level, region_name = EXCLUDED.region_name, "
        "rent_per_sqm_krw = EXCLUDED.rent_per_sqm_krw, "
        "vacancy_rate = COALESCE(EXCLUDED.vacancy_rate, rent_benchmarks.vacancy_rate), "
        "income_return = COALESCE(EXCLUDED.income_return, rent_benchmarks.income_return), "
        "capital_return = COALESCE(EXCLUDED.capital_return, rent_benchmarks.capital_return), "
        "investment_return = COALESCE(EXCLUDED.investment_return, rent_benchmarks.investment_return), "
        "collected_at = now()"
    ), rows)


def upsert_key_money(conn, rows: list[dict]) -> None:
    conn.execute(text(
        "INSERT INTO key_money_benchmarks (year, region_name, industry_group, key_money_ratio, avg_krw, "
        "median_krw, per_sqm_avg_krw) VALUES (:year, :region_name, :industry_group, :key_money_ratio, "
        ":avg_krw, :median_krw, :per_sqm_avg_krw) "
        "ON CONFLICT (year, region_name, industry_group) DO UPDATE SET "
        "key_money_ratio = EXCLUDED.key_money_ratio, avg_krw = EXCLUDED.avg_krw, median_krw = EXCLUDED.median_krw, "
        "per_sqm_avg_krw = EXCLUDED.per_sqm_avg_krw, collected_at = now()"
    ), rows)


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] R-ONE 수집 시작 — 건물유형 {len(TABLES)}종", flush=True)
    engine = None if dry_run else create_engine(market_url())
    total = failures = 0
    for building_type, (rent_id, vacancy_id, return_id) in TABLES.items():
        try:
            rows = merge_rows(building_type, fetch_table(rent_id), fetch_table(vacancy_id), fetch_table(return_id))
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
    try:
        km = key_money_rows(fetch_table(KEY_MONEY_TABLE, cycle="YY"))
        years = sorted({r["year"] for r in km})
        print(f"권리금: {len(km)}행 (연도 {years[:1]}~{years[-1:]})", flush=True)
        total += len(km)
        if not dry_run and km:
            with engine.begin() as conn:
                upsert_key_money(conn, km)
    except Exception as e:
        print(f"  [경고] 권리금 실패({e}) — 계속", flush=True)
        failures += 1
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 합계 {total}행"
          + (" (dry-run — 적재 생략)" if dry_run else "")
          + (f" / 실패 {failures}종" if failures else ""), flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
