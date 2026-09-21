"""OHLCV 수집 — yfinance 5분봉·일봉 → 허브 /automation/prices 적재.

뉴스(collect_news.py)와 같은 워치리스트를 공유해 뉴스↔주가 라벨 조인 커버리지를 보장한다.
스포크를 직접 만지지 않고 허브 HTTP 계약만 호출한다 — 중복은 서버((ticker, timeframe, ts)
유니크)가 걸러낸다. 매 실행이 겹침 창을 다시 받아 upsert하므로 실행 누락은 자가치유된다.

타임프레임 2종:
  5m — 뉴스 단기 반응(+30분/+1시간) 라벨용. yfinance 소급 한도 60일.
  1d — 익일/주간 라벨용. 소급 무제한(period=max).

백필 깊이는 허브 /automation/prices/coverage로 판단한다:
  보유 봉 없음(신규 티커) → 5m 60일 · 1d 전체 백필 / 보유 중 → 5m 5일 · 1d 1개월 겹침 재수집.

실행:
    python scripts/collect_prices.py            # 수집 + 허브 POST
    python scripts/collect_prices.py --dry-run  # 수집 결과 출력만 (허브 불요)

백엔드 PC cron 예시(1시간 주기):
    5 * * * * cd /path/to/minseok && ../venv/bin/python scripts/collect_prices.py >> ~/collect_prices.log 2>&1
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import logging

import requests
import yfinance as yf

from collect_news import load_watchlist

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))

from core.key.secret_manager import get_secret_manager  # noqa: E402
from stock.domain.services.bar_completeness import daily_bar_complete_after  # noqa: E402 — 순수 모듈(경량 venv에서도 import된다)

_secrets = get_secret_manager()

HUB_URL = _secrets.get("HUB_URL", "http://localhost:8000")
TOKEN = _secrets.get("N8N_INBOUND_TOKEN")
HEADERS = {"X-Webhook-Token": TOKEN}

# (timeframe, 봉 길이, 겹침 재수집 기간, 신규 티커 백필 기간)
TIMEFRAMES = [
    ("5m", timedelta(minutes=5), "5d", "60d"),
    ("1d", timedelta(days=1), "1mo", "max"),
]

# 시장 지수 — 레짐 판정용(SPY 200일선·VIX 수준). 워치리스트에 넣지 않는 이유:
# collect_news가 같은 목록을 공유해 지수 이름으로 뉴스를 긁어 학습 코퍼스를 오염시킨다.
# 일봉만 수집(5m은 레짐 판정에 불필요, 소급 60일 한도만 낭비).
INDEX_TICKERS = ["SPY", "^VIX"]


def fetch_coverage() -> dict[tuple[str, str], int]:
    """(ticker, timeframe) → 보유 봉 수. 백필 깊이 판단 근거."""
    res = requests.get(f"{HUB_URL}/automation/prices/coverage", headers=HEADERS, timeout=30)
    res.raise_for_status()
    return {(c["ticker"], c["timeframe"]): c["bars"] for c in res.json()}


def fetch_bars(ticker: str, timeframe: str, duration: timedelta, period: str) -> list[dict]:
    history = yf.Ticker(ticker).history(period=period, interval=timeframe, auto_adjust=True)
    if history.empty:
        return []
    history.index = history.index.tz_convert("UTC")
    now = datetime.now(timezone.utc)
    items = []
    # 일봉은 "시작 + 24시간"이 아니라 장 마감 뒤에 완성된다 — 분석과 같은 규칙(bar_completeness)으로 본다.
    # 예전 규칙은 한국 마감 봉을 다음 날 새벽에야, 미국 마감 봉을 8시간 뒤에야 담았다(2026-09-21 실측).
    complete_after = daily_bar_complete_after(ticker) if timeframe == "1d" else duration
    for ts, row in history.iterrows():
        # 진행 중(미완성) 봉 제외 — DO NOTHING upsert라 한번 저장된 봉은 갱신되지 않는다
        if ts + complete_after > now:
            continue
        if row[["Open", "High", "Low", "Close"]].isna().any():
            continue
        items.append({
            "ticker": ticker,
            "timeframe": timeframe,
            "ts": ts.isoformat(),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": 0 if row.isna()["Volume"] else int(row["Volume"]),
        })
    return items


def post_bars(items: list[dict]) -> int:
    if not items:
        return 0
    res = requests.post(
        f"{HUB_URL}/automation/prices", json={"items": items}, headers=HEADERS, timeout=120
    )
    res.raise_for_status()
    return res.json()["saved"]


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 수집 시작", flush=True)  # cron 로그 일자별 추적용
    coverage = {} if dry_run else fetch_coverage()
    total_fetched = total_saved = failures = 0
    # 워치리스트 종목(전 타임프레임) + 레짐용 지수(1d만)
    targets = [(ticker, TIMEFRAMES) for _, ticker, _ in load_watchlist() if ticker]
    targets += [(ticker, TIMEFRAMES[1:]) for ticker in INDEX_TICKERS]
    for ticker, timeframes in targets:
        counts = []
        for timeframe, duration, overlap_period, backfill_period in timeframes:
            period = overlap_period if (ticker, timeframe) in coverage else backfill_period
            try:  # 소스 단위 실패는 건너뛰고 계속 — cron 무인 실행 전제
                items = fetch_bars(ticker, timeframe, duration, period)
                total_fetched += len(items)
                if dry_run:
                    counts.append(f"{timeframe} {len(items)}봉({period})")
                    continue
                saved = post_bars(items)
                total_saved += saved
                counts.append(f"{timeframe} {len(items)}봉({period}) 신규 {saved}")
            except Exception as e:
                counts.append(f"{timeframe} 실패({e})")
                failures += 1
        print(f"{ticker}: " + " · ".join(counts), flush=True)
    print(
        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 합계: 수집 {total_fetched}봉"
        + ("" if dry_run else f" / 신규 저장 {total_saved}봉")
        + (f" / 실패 {failures}건" if failures else ""),
        flush=True,
    )
    return 1 if failures else 0


if __name__ == "__main__":
    # 부분 실패도 종료코드 1 — cron·감시가 실패를 관측할 수 있어야 한다.
    sys.exit(main())
