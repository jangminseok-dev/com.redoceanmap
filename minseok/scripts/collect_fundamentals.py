"""펀더멘털 스냅샷 수집 — yfinance(.info) + DART(한국 재무제표) → 허브 /automation/fundamentals 적재.

가격 파생(기술적) 지표와 별개의 축: 기업 가치·체력(PER/PBR/ROE/부채비율/FCF/EPS/BPS)을
주 1회 스냅샷으로 축적한다(뉴스·봉과 같은 발자국 — 스포크를 직접 만지지 않고 허브 HTTP 계약만).
중복은 서버((ticker, as_of, source) 유니크)가 걸러낸다.

소스 2종 (전부 무료):
  1. yfinance .info — 미국 종목은 전 지표, 한국 종목은 ROE·부채비율·FCF·시총만 줌(PER/PBR/EPS 결측)
  2. DART OpenAPI — 한국 종목의 재무제표로 EPS/BPS를 구해 PER/PBR을 자체 계산 (별도 행, source=dart)
     - BS(자본총계)는 최신 보고서, IS(당기순이익·주당이익)는 최신 사업보고서(연간) 기준 —
       분기 EPS로 PER을 내면 왜곡되므로 연간만 쓴다.
     - DART_API_KEY(루트 .env) 없으면 DART는 건너뛰고 yfinance만 적재(열화 동작).

실행:
    python scripts/collect_fundamentals.py            # 수집 + 허브 POST
    python scripts/collect_fundamentals.py --dry-run  # 수집 결과 출력만 (허브 불요)

백엔드 PC cron 예시(주 1회 월요일 03:00):
    0 3 * * 1 cd /path/to/minseok && ../venv/bin/python scripts/collect_fundamentals.py >> ~/collect_fundamentals.log 2>&1
"""

import io
import json
import logging
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime
from pathlib import Path

import requests
import yfinance as yf

from collect_news import load_watchlist

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))

from core.key.secret_manager import get_secret_manager  # noqa: E402

_secrets = get_secret_manager()

HUB_URL = _secrets.get("HUB_URL", "http://localhost:8000")
TOKEN = _secrets.get("N8N_INBOUND_TOKEN")
DART_API_KEY = _secrets.get("DART_API_KEY")
DART_URL = "https://opendart.fss.or.kr/api"
CORP_CODE_CACHE = ROOT / "scripts" / "dart_corp_codes.json"
CORP_CODE_TTL_DAYS = 30
# 보고서 코드: 11011 사업(연간) · 11012 반기 · 11013 1분기 · 11014 3분기
QUARTER_ORDER = ("11014", "11012", "11013")


def yfinance_snapshot(ticker: str) -> tuple[dict | None, float | None]:
    """yfinance .info → (스냅샷 항목, 현재가). 한국 종목은 PER/PBR/EPS가 None인 게 정상."""
    info = yf.Ticker(ticker).info
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    fields = {
        "per": info.get("trailingPE"),
        "pbr": info.get("priceToBook"),
        "roe": info.get("returnOnEquity"),
        "debtToEquity": info.get("debtToEquity"),
        "fcf": info.get("freeCashflow"),
        "marketCap": info.get("marketCap"),
        "eps": info.get("trailingEps"),
        "bps": info.get("bookValue"),
    }
    if all(v is None for v in fields.values()):
        return None, price
    return {"ticker": ticker, "asOf": date.today().isoformat(), "source": "yfinance",
            **{k: (float(v) if v is not None else None) for k, v in fields.items()}}, price


def load_corp_codes() -> dict[str, str]:
    """종목코드(6자리) → DART 고유번호(8자리) 매핑. 30일 캐시."""
    if CORP_CODE_CACHE.exists():
        age_days = (time.time() - CORP_CODE_CACHE.stat().st_mtime) / 86400
        if age_days < CORP_CODE_TTL_DAYS:
            return json.loads(CORP_CODE_CACHE.read_text(encoding="utf-8"))
    res = requests.get(f"{DART_URL}/corpCode.xml", params={"crtfc_key": DART_API_KEY}, timeout=60)
    res.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        xml_bytes = zf.read(zf.namelist()[0])
    mapping = {}
    for corp in ET.fromstring(xml_bytes).findall("list"):
        stock_code = (corp.findtext("stock_code") or "").strip()
        if stock_code:
            mapping[stock_code] = (corp.findtext("corp_code") or "").strip()
    CORP_CODE_CACHE.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")
    return mapping


def _amount(row: dict) -> float | None:
    raw = (row.get("thstrm_amount") or "").replace(",", "").strip()
    try:
        return float(raw)
    except ValueError:
        return None


def _fetch_statements(corp_code: str, year: int, reprt_code: str) -> list[dict]:
    for fs_div in ("CFS", "OFS"):  # 연결 우선, 없으면 개별
        res = requests.get(f"{DART_URL}/fnlttSinglAcntAll.json", params={
            "crtfc_key": DART_API_KEY, "corp_code": corp_code,
            "bsns_year": str(year), "reprt_code": reprt_code, "fs_div": fs_div,
        }, timeout=30)
        res.raise_for_status()
        body = res.json()
        if body.get("status") == "000":
            return body.get("list", [])
    return []


def _pick(rows: list[dict], sj_divs: tuple[str, ...], names: tuple[str, ...]) -> float | None:
    for row in rows:
        if row.get("sj_div") in sj_divs and any(row.get("account_nm", "").startswith(n) for n in names):
            value = _amount(row)
            if value is not None:
                return value
    return None


def dart_snapshot(ticker: str, corp_codes: dict[str, str], price: float | None,
                  market_cap: float | None) -> dict | None:
    """DART 재무제표 → EPS/BPS/ROE + (현재가로) PER/PBR 자체 계산. 한국 종목 전용."""
    stock_code = ticker.split(".")[0]
    corp_code = corp_codes.get(stock_code)
    if not corp_code:
        return None
    year = datetime.now().year

    # IS: 최신 사업보고서(연간) — 분기 EPS/순이익으로 PER·ROE를 내면 왜곡
    annual = next((rows for y in (year - 1, year - 2)
                   if (rows := _fetch_statements(corp_code, y, "11011"))), [])
    # 계정명이 회사별로 다름: 삼성전자 "기본주당이익", SK하이닉스 "기본주당순이익(손실)"
    eps = _pick(annual, ("IS", "CIS"), ("기본주당이익", "기본주당순이익"))
    net_income = _pick(annual, ("IS", "CIS"), ("당기순이익",))

    # BS: 최신 보고서(분기 포함) — 재무상태표는 시점 값이라 최신이 정확
    latest = annual
    for reprt_code in QUARTER_ORDER:
        if rows := _fetch_statements(corp_code, year, reprt_code):
            latest = rows
            break
    equity = _pick(latest, ("BS",), ("자본총계",))

    shares = market_cap / price if market_cap and price else None
    bps = equity / shares if equity and shares else None
    item = {
        "ticker": ticker, "asOf": date.today().isoformat(), "source": "dart",
        "eps": eps, "bps": bps,
        "per": price / eps if price and eps and eps > 0 else None,
        "pbr": price / bps if price and bps and bps > 0 else None,
        "roe": net_income / equity if net_income is not None and equity else None,
        "marketCap": market_cap,
    }
    return item if any(item[k] is not None for k in ("eps", "bps", "per", "pbr", "roe")) else None


def post_to_hub(items: list[dict]) -> dict:
    res = requests.post(
        f"{HUB_URL}/automation/fundamentals",
        json={"items": items},
        headers={"X-Webhook-Token": TOKEN},
        timeout=30,
    )
    res.raise_for_status()
    return res.json()


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 펀더멘털 수집 시작", flush=True)
    failures = 0
    corp_codes: dict[str, str] = {}
    if DART_API_KEY:
        try:
            corp_codes = load_corp_codes()
        except Exception as e:
            print(f"DART corp_code 매핑 실패 — yfinance만 진행: {e}")
            failures += 1
    else:
        print("DART_API_KEY 없음 — yfinance만 적재 (키는 opendart.fss.or.kr 무료 발급)")

    items: list[dict] = []
    for name, ticker, _ in load_watchlist():
        if not ticker:
            continue
        counts = []
        price = market_cap = None
        try:  # 소스 단위 실패는 건너뛰고 계속 — cron 무인 실행 전제
            snapshot, price = yfinance_snapshot(ticker)
            if snapshot:
                market_cap = snapshot["marketCap"]
                items.append(snapshot)
                counts.append("yfinance ✓")
        except Exception as e:
            counts.append(f"yfinance 실패({e})")
            failures += 1
        if corp_codes and ticker.split(".")[0].isdigit():
            try:
                snapshot = dart_snapshot(ticker, corp_codes, price, market_cap)
                if snapshot:
                    items.append(snapshot)
                    counts.append("dart ✓")
            except Exception as e:
                counts.append(f"dart 실패({e})")
                failures += 1
        print(f"{name}({ticker}): " + " · ".join(counts or ["지표 없음"]))
        if dry_run and items:
            latest_items = [i for i in items if i["ticker"] == ticker]
            for it in latest_items:
                shown = {k: v for k, v in it.items() if k not in ("ticker", "asOf") and v is not None}
                print(f"  - {shown}")

    if dry_run:
        print(f"[dry-run] 스냅샷 {len(items)}건 생성 — POST 생략", flush=True)
        return 1 if failures else 0
    try:
        result = post_to_hub(items)
        print(
            f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 합계: 수집 {len(items)} / 신규 저장 {result['saved']}"
            + (f" / 실패 {failures}건" if failures else ""),
            flush=True,
        )
    except Exception as e:
        print(f"허브 POST 실패 — {e}", flush=True)
        failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    # 부분 실패도 종료코드 1 — cron·감시가 실패를 관측할 수 있어야 한다.
    sys.exit(main())
