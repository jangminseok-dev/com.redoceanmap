"""과거 펀더멘털 백필 — yfinance 연간 재무제표(4개 회계연도) → 허브 /automation/fundamentals 적재.

주간 수집(collect_fundamentals.py)은 "지금" 스냅샷만 쌓아 5주치뿐이다 — 분기 지평
백테스트(E2)에는 과거가 필요하다. yfinance 연간 재무제표는 미국·한국 모두 최근
4개 회계연도를 소급 제공한다(2026-08-21 실측: AAPL 4년 + 005930.KS 4년) —
DART 소급 경로는 한국 2종목뿐이라 만들지 않는다(단일 경로 유지).

point-in-time 규칙 (백테스트 룩어헤드 방지의 핵심):
  as_of = 회계연도 말 + 90일 (공시 시차 보수 추정 — 미국 10-K 제출기한 60~90일,
  한국 사업보고서 90일). 회계연도 말 시점으로 넣으면 아직 공시되지 않은 실적을
  아는 셈이 된다. +90일이 오늘을 넘는 연도는 건너뛴다.

행 규칙: source='yf-hist' 별도 행(주간 'yfinance' 행과 (ticker, as_of, source) 유니크로
공존). eps·bps·roe만 채운다 — per/pbr는 시점 가격 파생이라 백테스트가 price_bars로
그날그날 계산한다(여기 넣으면 as_of 하루 가격에 고정된 반쪽 값이 된다).

실행:
    python scripts/backfill_fundamentals.py            # 수집 + 허브 POST
    python scripts/backfill_fundamentals.py --dry-run  # 수집 결과 출력만

수동 실행 전용(E2 백테스트 준비) — cron 불요. 재실행은 유니크 제약으로 멱등.
"""

import logging
import sys
from datetime import date, datetime, timedelta
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

FILING_LAG_DAYS = 90  # 회계연도 말 → 공시 가용 추정 시차(보수)


def _row(frame, *names: str):
    """계정 행 하나 — 이름 후보 순서대로 첫 존재 행. 없으면 None."""
    for name in names:
        if name in frame.index:
            return frame.loc[name]
    return None


def annual_snapshots(ticker: str) -> list[dict]:
    t = yf.Ticker(ticker)
    inc, bal = t.income_stmt, t.balance_sheet
    if inc is None or inc.empty:
        return []  # 지수(SPY·^VIX) 등 재무제표 없음 — 자연 제외

    eps_row = _row(inc, "Basic EPS")
    net_row = _row(inc, "Net Income")
    shares_row = _row(inc, "Basic Average Shares")
    equity_row = _row(bal, "Stockholders Equity", "Common Stock Equity") if not bal.empty else None
    issued_row = _row(bal, "Ordinary Shares Number", "Share Issued") if not bal.empty else None

    out: list[dict] = []
    for col in inc.columns:  # 회계연도 말(Timestamp) — 최신부터
        fiscal_end = col.date()
        as_of = fiscal_end + timedelta(days=FILING_LAG_DAYS)
        if as_of > date.today():
            continue  # 공시 가용 추정일이 미래 — point-in-time 규칙상 제외

        def _v(row):
            if row is None or col not in row.index:
                return None
            value = row[col]
            return float(value) if value == value else None  # NaN 방어

        eps = _v(eps_row)
        net_income, avg_shares = _v(net_row), _v(shares_row)
        if eps is None and net_income is not None and avg_shares:
            eps = net_income / avg_shares  # Basic EPS 결측 종목 폴백
        equity, issued = _v(equity_row), _v(issued_row)
        shares = issued or avg_shares
        bps = equity / shares if equity is not None and shares else None
        roe = net_income / equity if net_income is not None and equity else None

        if eps is None and bps is None and roe is None:
            continue
        out.append({
            "ticker": ticker, "asOf": as_of.isoformat(), "source": "yf-hist",
            "eps": eps, "bps": bps, "roe": roe,
        })
    return out


def post_to_hub(items: list[dict]) -> dict:
    res = requests.post(
        f"{HUB_URL}/automation/fundamentals",
        json={"items": items},
        headers={"X-Webhook-Token": TOKEN},
        timeout=60,
    )
    res.raise_for_status()
    return res.json()


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 과거 펀더멘털 백필 시작", flush=True)
    items: list[dict] = []
    failures = 0
    for name, ticker, _ in load_watchlist():
        if not ticker:
            continue
        try:  # 종목 단위 실패는 건너뛰고 계속
            rows = annual_snapshots(ticker)
        except Exception as e:
            print(f"{name}({ticker}): 실패({e})")
            failures += 1
            continue
        items.extend(rows)
        print(f"{name}({ticker}): {len(rows)}개 연도" + (
            f" ({rows[-1]['asOf']}~{rows[0]['asOf']})" if rows else " — 재무제표 없음"))

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
    sys.exit(main())
