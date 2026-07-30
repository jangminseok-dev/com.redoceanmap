"""뉴스 수집 — Google News RSS(한/영) + yfinance 기관 등급·목표가 → 허브 /automation/news 적재.

n8n 뉴스 워크플로를 대체하는 독립 스크립트(발자국: ingest_seoul_3nf.py 컨벤션).
스포크를 직접 만지지 않고 허브 HTTP 계약만 호출한다 — 중복은 서버(url 유니크)가 걸러낸다.

소스 3종 (전부 무료):
  1. 한글 Google News RSS — 한국 언론 헤드라인
  2. 영문 Google News RSS — Bloomberg/Reuters/CNBC 등 해외 헤드라인 집계
  3. yfinance upgrades_downgrades — 기관 투자의견·목표가 상/하향 이벤트(최근 7일)

실행:
    python scripts/collect_news.py            # RSS 2종 수집 + 허브 POST
    python scripts/collect_news.py --analyst  # 기관 등급·목표가(yfinance)까지 포함
    python scripts/collect_news.py --dry-run  # 수집 결과 출력만 (허브 불요)

백엔드 PC cron 예시 — 기관등급은 일 1회로 분리(워치리스트 수십 종 × 30분이면
yfinance 429 위험이라 RSS만 고빈도로 돈다). flock으로 네트워크 저하 시 중첩 실행을 막는다:
    */30 * * * * flock -n /tmp/collect_news.lock -c 'cd /path/to/minseok && ../venv/bin/python scripts/collect_news.py' >> ~/collect_news.log 2>&1
    10 7 * * *   flock -n /tmp/collect_news.lock -c 'cd /path/to/minseok && ../venv/bin/python scripts/collect_news.py --analyst' >> ~/collect_news.log 2>&1
"""

import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

import logging

import requests
import yfinance as yf

logging.getLogger("yfinance").setLevel(logging.CRITICAL)  # .KS 등 미지원 종목 404 소음 억제

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))

from core.key.secret_manager import get_secret_manager  # noqa: E402

_secrets = get_secret_manager()

HUB_URL = _secrets.get("HUB_URL", "http://localhost:8000")
TOKEN = _secrets.get("N8N_INBOUND_TOKEN")
WATCHLIST = ROOT / "scripts" / "news_watchlist.txt"
RSS_KR = "https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
RSS_EN = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
MAX_PER_QUERY = 20
ANALYST_WINDOW_DAYS = 7
REQUEST_DELAY_SECONDS = 0.5  # 종목 간 딜레이 — 단일 IP 무딜레이 버스트는 Google 소프트밴 위험

ACTION_KR = {"up": "상향", "down": "하향", "main": "유지", "reit": "재확인", "init": "신규 커버"}


def load_watchlist() -> list[tuple[str, str, str]]:
    """(한글명, 티커, 영문쿼리) 목록. 영문쿼리 생략 시 '{티커} stock'."""
    entries = []
    for line in WATCHLIST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        name = parts[0]
        ticker = parts[1] if len(parts) > 1 else ""
        en_query = parts[2] if len(parts) > 2 else (f"{ticker} stock" if ticker else "")
        entries.append((name, ticker, en_query))
    return entries


def fetch_google_rss(rss_template: str, query: str, ticker: str) -> list[dict]:
    url = rss_template.format(q=urllib.parse.quote(query))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as res:
        root = ET.fromstring(res.read())

    items = []
    for item in root.findall(".//item")[:MAX_PER_QUERY]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        source = (item.findtext("source") or "").strip()
        if title.endswith(f" - {source}"):  # Google News는 제목 뒤에 언론사를 붙인다
            title = title[: -len(f" - {source}")].strip()
        published = None
        pub_date = item.findtext("pubDate")
        if pub_date:
            try:
                published = parsedate_to_datetime(pub_date).isoformat()
            except (TypeError, ValueError):
                pass
        if title and link:
            items.append({
                "title": title,  # 원문 그대로 — 종목 귀속은 ticker 필드가 담당(학습 입력 오염 방지)
                "source": source or "google-news",
                "url": link,
                "ticker": ticker,
                "publishedAt": published,
            })
    return items


def fetch_analyst_actions(name: str, ticker: str) -> list[dict]:
    """기관 투자의견·목표가 변경(최근 N일)을 뉴스 아이템으로 변환."""
    ud = yf.Ticker(ticker).upgrades_downgrades
    if ud is None or ud.empty:
        return []
    cutoff = datetime.now() - timedelta(days=ANALYST_WINDOW_DAYS)
    items = []
    for grade_date, row in ud[ud.index >= cutoff].iterrows():
        action = ACTION_KR.get(str(row.get("Action", "")), str(row.get("Action", "")))
        title = f"{name} — {row['Firm']} 투자의견 {row['ToGrade']} ({action})"
        cur, prior = row.get("currentPriceTarget", 0) or 0, row.get("priorPriceTarget", 0) or 0
        if cur > 0:
            title += f", 목표가 ${prior:g}→${cur:g}" if prior > 0 else f", 목표가 ${cur:g}"
        firm_slug = str(row["Firm"]).replace(" ", "-").lower()
        items.append({
            "title": title,
            "source": str(row["Firm"]),
            # 실제 기사 URL이 없는 이벤트 — 티커·시각·기관으로 합성해 유니크 중복 차단에 태운다
            "url": f"analyst://{ticker}/{grade_date:%Y%m%d%H%M%S}/{firm_slug}",
            "ticker": ticker,
            "publishedAt": grade_date.isoformat(),
        })
    return items


def post_to_hub(items: list[dict]) -> dict:
    res = requests.post(
        f"{HUB_URL}/automation/news",
        json={"items": items},
        headers={"X-Webhook-Token": TOKEN},
        timeout=30,
    )
    res.raise_for_status()
    return res.json()


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    with_analyst = "--analyst" in sys.argv  # yfinance 호출 절감 — 일 1회 cron에서만 켠다
    mode = "RSS+기관등급" if with_analyst else "RSS만 (기관등급은 --analyst 실행에서)"
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 수집 시작 — {mode}", flush=True)  # cron 로그 추적용
    total_fetched = total_saved = failures = 0
    for name, ticker, en_query in load_watchlist():
        items: list[dict] = []
        sources = [("한글뉴스", lambda: fetch_google_rss(RSS_KR, name, ticker))]
        if en_query:
            sources.append(("영문뉴스", lambda: fetch_google_rss(RSS_EN, en_query, ticker)))
        if ticker and with_analyst:
            sources.append(("기관등급", lambda: fetch_analyst_actions(name, ticker)))
        counts = []
        for label, fetch in sources:
            try:  # 소스 단위 실패는 건너뛰고 계속 — cron 무인 실행 전제
                got = fetch()
                items += got
                counts.append(f"{label} {len(got)}")
            except Exception as e:
                counts.append(f"{label} 실패({e})")
                failures += 1
        total_fetched += len(items)
        time.sleep(REQUEST_DELAY_SECONDS)
        line = f"{name}: " + " · ".join(counts)
        if dry_run:
            print(line)
            for it in items[:2] + [i for i in items if i["url"].startswith("analyst://")][:2]:
                print(f"  - {it['title'][:90]} ({it['source']})")
            continue
        try:
            result = post_to_hub(items)
            total_saved += result["saved"]
            print(f"{line} → 신규 저장 {result['saved']}")
        except Exception as e:
            print(f"{line} → 허브 POST 실패 — {e}")
            failures += 1
    print(
        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 합계: 수집 {total_fetched}"
        + ("" if dry_run else f" / 신규 저장 {total_saved}")
        + (f" / 실패 {failures}건" if failures else ""),
        flush=True,
    )
    return 1 if failures else 0


if __name__ == "__main__":
    # 부분 실패도 종료코드 1 — cron·감시가 실패를 관측할 수 있어야 한다.
    sys.exit(main())
