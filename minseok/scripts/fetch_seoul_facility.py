"""집객시설-상권(OA-15580) 수집 — 서울 열린데이터광장 OpenAPI → CSV.

이 데이터셋만 **포털에 파일 다운로드가 없다**(다른 10종은 연도별/전체 zip 제공).
남은 경로가 OpenAPI뿐이라 여기서 받아 다른 CSV와 같은 자리·같은 인코딩으로 떨궈,
`ingest_seoul_3nf.py`가 나머지 팩트와 동일하게 적재하도록 한다.

헤더는 API 필드 코드(STDR_YYQU_CD 등)를 그대로 쓴다 — 포털이 한글 라벨을 공개하지
않아 지어내지 않는다(`column_maps.FACILITY_COLUMN_MAP`이 이 코드를 매핑한다).

    python scripts/fetch_seoul_facility.py            # 전량 수집 후 CSV 저장
    python scripts/fetch_seoul_facility.py --dry-run  # 총건수·분기 분포만 확인
"""

import argparse
import csv
import sys
import time
import urllib.request
from collections import Counter
from json import loads
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))
from core.key.secret_manager import get_secret_manager  # noqa: E402

SERVICE = "VwsmTrdarFcltyQq"
PAGE = 1000  # OpenAPI 1회 최대 건수
OUT = ROOT / "data" / "raw" / "seoul" / "서울시 상권분석서비스(집객시설-상권).csv"
ENC = "cp949"  # 다른 상권 CSV와 동일 — ingest가 이 인코딩으로 읽는다


def _fetch(key: str, start: int, end: int) -> dict:
    url = f"http://openapi.seoul.go.kr:8088/{key}/json/{SERVICE}/{start}/{end}/"
    with urllib.request.urlopen(url, timeout=60) as res:
        return loads(res.read().decode("utf-8"))[SERVICE]


def main(dry_run: bool) -> None:
    key = get_secret_manager().require("SEOUL_OPENDATA_API_KEY")

    head = _fetch(key, 1, 1)
    total = head["list_total_count"]
    fields = list(head["row"][0].keys())
    print(f"총 {total:,}건 · 컬럼 {len(fields)}개")

    rows: list[dict] = []
    for start in range(1, total + 1, PAGE):
        end = min(start + PAGE - 1, total)
        for attempt in (1, 2, 3):  # 공공 API는 간헐적으로 끊긴다 — 짧게 재시도
            try:
                rows.extend(_fetch(key, start, end)["row"])
                break
            except Exception as e:
                if attempt == 3:
                    raise
                print(f"  {start}-{end} 재시도 {attempt}: {e}")
                time.sleep(2)
        print(f"  {len(rows):,}/{total:,}", end="\r", flush=True)
    print()

    quarters = Counter(r["STDR_YYQU_CD"] for r in rows)
    print(f"분기 {len(quarters)}개: {min(quarters)}~{max(quarters)}")
    print(f"상권 {len({r['TRDAR_CD'] for r in rows}):,}곳")

    if dry_run:
        print("dry-run — 저장하지 않음")
        return

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding=ENC, newline="", errors="replace") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"저장: {OUT.name} ({OUT.stat().st_size:,}B)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="집객시설-상권 OpenAPI 수집")
    ap.add_argument("--dry-run", action="store_true", help="저장 없이 총건수·분기만 확인")
    main(ap.parse_args().dry_run)
