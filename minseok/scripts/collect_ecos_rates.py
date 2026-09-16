"""한국은행 ECOS 금리 수집 — 기준금리(722Y001)·예금은행 대출금리(121Y006) 월별 → interest_rates.

창업 재무 엔진의 이자 계산 원천(대출평균). 전국 값이라 상권 매칭이 없다.
멱등 규칙: (stat_code, item_name, year_month) upsert. 기본 실행은 최근 REFRESH_MONTHS(3)개월 재수집.

실행 (백엔드 이미지 파드):
    kubectl -n redocean exec deploy/backend -- python scripts/collect_ecos_rates.py            # 최근 3개월
    ... python scripts/collect_ecos_rates.py --from 202001                                    # 백필
    ... python scripts/collect_ecos_rates.py --dry-run

스케줄(매월 15일 04:00 — 한은 공표 뒤):
    infra/k8s/overlays/prod/cronjobs/collect-ecos-rates.yaml
"""

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.request import urlopen

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))
from core.key.secret_manager import get_secret_manager  # noqa: E402

_secrets = get_secret_manager()

API_URL = "https://ecos.bok.or.kr/api/StatisticSearch"
REFRESH_MONTHS = 3
# 통계코드 → 남길 항목명(정규화 후). 기업대출은 소상공인 근사치 후보로 같이 둔다.
WANTED = {
    "722Y001": ("한국은행 기준금리",),
    "121Y006": ("대출평균", "기업대출"),
}
_FOOTNOTE = re.compile(r"\s*\d\)\s*$")


def market_url() -> str:
    url = _secrets.get("MARKET_DATABASE_URL") or _secrets.require("DATABASE_URL")
    return url.replace("postgresql://", "postgresql+psycopg://")


def normalize_item(name: str) -> str:
    """"대출평균 1)" → "대출평균" (ECOS 각주 번호 제거)."""
    return _FOOTNOTE.sub("", name).strip()


def to_rows(raw: list[dict]) -> list[dict]:
    out = []
    for r in raw:
        code = r.get("STAT_CODE", "")
        item = normalize_item(r.get("ITEM_NAME1", ""))
        if item not in WANTED.get(code, ()):
            continue
        try:
            rate = float(r["DATA_VALUE"])
        except (KeyError, ValueError):
            continue
        out.append({"stat_code": code, "item_name": item, "year_month": int(r["TIME"]), "rate": rate})
    return out


def fetch(stat_code: str, start_ym: str, end_ym: str) -> list[dict]:
    key = _secrets.require("ECOS_API_KEY")
    url = f"{API_URL}/{key}/json/kr/1/1000/{stat_code}/M/{start_ym}/{end_ym}"
    with urlopen(url, timeout=60) as res:
        body = json.loads(res.read().decode("utf-8"))
    if "RESULT" in body:
        raise RuntimeError(f"{stat_code}: {body['RESULT']}")
    return body.get("StatisticSearch", {}).get("row", [])


def upsert(conn, rows: list[dict]) -> None:
    conn.execute(text(
        "INSERT INTO interest_rates (stat_code, item_name, year_month, rate) "
        "VALUES (:stat_code, :item_name, :year_month, :rate) "
        "ON CONFLICT (stat_code, item_name, year_month) DO UPDATE SET rate = EXCLUDED.rate, collected_at = now()"
    ), rows)


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    today = date.today()
    end_ym = f"{today.year}{today.month:02d}"
    if "--from" in sys.argv:
        start_ym = sys.argv[sys.argv.index("--from") + 1]
    else:
        back = today.year * 12 + today.month - 1 - (REFRESH_MONTHS - 1)
        start_ym = f"{back // 12}{back % 12 + 1:02d}"
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] ECOS 수집 시작 — {start_ym}~{end_ym}", flush=True)
    engine = None if dry_run else create_engine(market_url())
    total = failures = 0
    for code in WANTED:
        try:
            rows = to_rows(fetch(code, start_ym, end_ym))
        except Exception as e:
            print(f"  [경고] {code} 실패({e}) — 계속", flush=True)
            failures += 1
            continue
        print(f"{code}: {len(rows)}행", flush=True)
        total += len(rows)
        if not dry_run and rows:
            with engine.begin() as conn:
                upsert(conn, rows)
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 합계 {total}행"
          + (" (dry-run — 적재 생략)" if dry_run else "")
          + (f" / 실패 {failures}건" if failures else ""), flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
