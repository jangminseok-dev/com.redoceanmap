"""국토부 상업업무용 매매 실거래 수집 — 서울 25개 자치구 × 월 단위 → commercial_trades.

상권 축의 비용 공백(진입 비용)을 메운다. API는 RTMSDataSvcNrgTrade(DATA_GO_KR_API_KEY),
XML 응답. **임대(전월세)는 공개 API에 없다**(2026-08-21 확인 — RTMSDataSvcNrgRent 등
NO_OPENAPI_SERVICE) — 매매만 적재하고, 임대료 축은 한국부동산원 R-ONE(별도 키)이 후속 후보.

멱등 규칙: 원본에 거래 고유 ID가 없다 — (자치구, 거래 연월) 단위로 DELETE 후 INSERT 교체.
해제 신고(cdealType='O')는 거래 몇 달 뒤 붙기도 하므로(6월 거래가 8월에 해제) 기본 실행이
최근 REFRESH_MONTHS(3)개월을 재수집해 해제를 반영한다. 해제 거래는 적재하지 않는다.

실행 (백엔드 이미지 파드 — 호스트 cron venv에는 sqlalchemy가 없다):
    kubectl -n redocean exec deploy/backend -- python scripts/collect_commercial_trades.py    # 최근 3개월
    ... python scripts/collect_commercial_trades.py --from 202301                             # 백필
    ... python scripts/collect_commercial_trades.py --dry-run                                 # 적재 없이 집계만

스케줄(매월 3일 04:30 — 실거래 신고 기한 30일이라 월 단위 갱신이면 충분):
    infra/k8s/overlays/prod/cronjobs/collect-commercial-trades.yaml  (수동: kubectl -n redocean create job --from=cronjob/collect-commercial-trades ...)
"""

import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path
from urllib.request import urlopen

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))
from core.key.secret_manager import get_secret_manager  # noqa: E402

_secrets = get_secret_manager()

API_URL = "http://apis.data.go.kr/1613000/RTMSDataSvcNrgTrade/getRTMSDataSvcNrgTrade"
PAGE_SIZE = 1000  # 자치구×월 거래가 수백 건 수준이라 사실상 1페이지
REFRESH_MONTHS = 3  # 기본 실행의 재수집 창 — 신고 지연(30일) + 해제 반영

# 서울 25개 자치구 법정동 시군구코드 — region 자치구 코드와 동일 체계(11680=강남구 확인)
SEOUL_SGG = [
    "11110", "11140", "11170", "11200", "11215", "11230", "11260", "11290", "11305",
    "11320", "11350", "11380", "11410", "11440", "11470", "11500", "11530", "11545",
    "11560", "11590", "11620", "11650", "11680", "11710", "11740",
]


def market_url() -> str:
    url = _secrets.get("MARKET_DATABASE_URL") or _secrets.require("DATABASE_URL")
    # 접두사가 빠지면 psycopg2를 찾다가 죽는다(다른 배치와 동일 규칙)
    return url.replace("postgresql://", "postgresql+psycopg://")


def month_range(start_ym: str, end: date) -> list[str]:
    """YYYYMM 시작 ~ end 월까지의 연월 목록."""
    year, month = int(start_ym[:4]), int(start_ym[4:6])
    out = []
    while (year, month) <= (end.year, end.month):
        out.append(f"{year}{month:02d}")
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return out


def _text(item: ET.Element, tag: str) -> str:
    return (item.findtext(tag) or "").strip()


def _num(raw: str) -> float | None:
    raw = raw.replace(",", "").strip()
    try:
        return float(raw)
    except ValueError:
        return None


def fetch_month(sgg_cd: str, deal_ymd: str) -> list[dict]:
    key = _secrets.require("DATA_GO_KR_API_KEY")
    rows: list[dict] = []
    page = 1
    while True:
        url = (f"{API_URL}?serviceKey={key}&LAWD_CD={sgg_cd}&DEAL_YMD={deal_ymd}"
               f"&numOfRows={PAGE_SIZE}&pageNo={page}")
        with urlopen(url, timeout=60) as res:
            root = ET.fromstring(res.read())
        code = root.findtext(".//resultCode") or root.findtext(".//returnReasonCode")
        if code not in ("000", "00"):
            raise RuntimeError(root.findtext(".//resultMsg")
                               or root.findtext(".//returnAuthMsg") or "알 수 없는 응답")
        items = root.findall(".//item")
        for item in items:
            if _text(item, "cdealType") == "O":
                continue  # 해제된 거래 — 성사되지 않은 가격을 시세에 섞지 않는다
            amount = _num(_text(item, "dealAmount"))
            area = _num(_text(item, "buildingAr"))
            year, month, day = (_num(_text(item, t)) for t in ("dealYear", "dealMonth", "dealDay"))
            if not amount or not area or area <= 0 or not (year and month and day):
                continue  # 금액·면적 결측은 평단가를 만들 수 없다
            floor = _num(_text(item, "floor"))
            build_year = _num(_text(item, "buildYear"))
            rows.append({
                "sgg_cd": _text(item, "sggCd") or sgg_cd,
                "sgg_nm": _text(item, "sggNm"),
                "umd_nm": _text(item, "umdNm"),
                "jibun": _text(item, "jibun") or None,
                "building_type": _text(item, "buildingType") or "미상",
                "building_use": _text(item, "buildingUse") or None,
                "land_use": _text(item, "landUse") or None,
                "floor": int(floor) if floor is not None else None,
                "build_year": int(build_year) if build_year is not None else None,
                "building_ar": area,
                "deal_amount": amount,
                "deal_date": date(int(year), int(month), int(day)),
            })
        total = int(root.findtext(".//totalCount") or 0)
        if page * PAGE_SIZE >= total:
            return rows
        page += 1


def replace_month(conn, sgg_cd: str, deal_ymd: str, rows: list[dict]) -> int:
    """(자치구, 연월) 파티션 교체 — 재수집 멱등 + 해제 반영의 근거."""
    first = date(int(deal_ymd[:4]), int(deal_ymd[4:6]), 1)
    next_first = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    conn.execute(text(
        "DELETE FROM commercial_trades WHERE sgg_cd = :sgg AND deal_date >= :a AND deal_date < :b"
    ), {"sgg": sgg_cd, "a": first, "b": next_first})
    if rows:
        conn.execute(text(
            "INSERT INTO commercial_trades (sgg_cd, sgg_nm, umd_nm, jibun, building_type, "
            "building_use, land_use, floor, build_year, building_ar, deal_amount, deal_date) "
            "VALUES (:sgg_cd, :sgg_nm, :umd_nm, :jibun, :building_type, :building_use, "
            ":land_use, :floor, :build_year, :building_ar, :deal_amount, :deal_date)"
        ), rows)
    return len(rows)


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    today = date.today()
    if "--from" in sys.argv:
        start_ym = sys.argv[sys.argv.index("--from") + 1]
    else:
        back = today.year * 12 + today.month - 1 - (REFRESH_MONTHS - 1)
        start_ym = f"{back // 12}{back % 12 + 1:02d}"
    months = month_range(start_ym, today)
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 수집 시작 — {months[0]}~{months[-1]} × 25구"
          f" ({len(months) * len(SEOUL_SGG)}요청)", flush=True)

    engine = None if dry_run else create_engine(market_url())
    total_rows = failures = 0
    for ym in months:
        month_count = 0
        for sgg in SEOUL_SGG:
            try:
                rows = fetch_month(sgg, ym)
            except Exception as e:
                print(f"  [경고] {sgg} {ym} 실패({e}) — 계속")
                failures += 1
                continue
            month_count += len(rows)
            if not dry_run:
                with engine.begin() as conn:
                    replace_month(conn, sgg, ym, rows)
        total_rows += month_count
        print(f"{ym}: {month_count}건", flush=True)

    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 합계 {total_rows}건"
          + (" (dry-run — 적재 생략)" if dry_run else "")
          + (f" / 실패 {failures}요청" if failures else ""), flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    # 부분 실패도 종료코드 1 — cron·감시가 실패를 관측할 수 있어야 한다.
    sys.exit(main())
