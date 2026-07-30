"""상권 뉴스 수집 — Google News RSS(한글) → 허브 /automation/market-news 적재.

주식 뉴스 수집기(collect_news.py)와 동일 컨벤션의 독립 스크립트.
스포크를 직접 만지지 않고 허브 HTTP 계약만 호출한다 — 중복은 서버((url, area_tag) 유니크)가 걸러낸다.

소스: 한글 Google News RSS — 워치리스트(지역 어간 × "상권" + 정책 공통 키워드).
지역 상권 기사는 시의성이 일 단위면 충분하므로 하루 1회 수집한다.

실행:
    python scripts/collect_market_news.py            # 수집 + 허브 POST
    python scripts/collect_market_news.py --dry-run  # 수집 결과 출력만 (허브 불요)

백엔드 PC cron 예시(매일 01:30 — 라벨링 02:30·펀더멘털 03:00과 겹치지 않게):
    30 1 * * * cd /path/to/minseok && ../venv/bin/python scripts/collect_market_news.py >> ~/collect_market_news.log 2>&1
"""

import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))

from core.key.secret_manager import get_secret_manager  # noqa: E402

_secrets = get_secret_manager()

HUB_URL = _secrets.get("HUB_URL", "http://localhost:8000")
TOKEN = _secrets.get("N8N_INBOUND_TOKEN")
WATCHLIST = ROOT / "scripts" / "market_news_watchlist.txt"
RSS_KR = "https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
MAX_PER_QUERY = 20


def load_watchlist() -> list[tuple[str, str]]:
    """(지역태그, 검색어) 목록. 검색어 생략 시 '{태그} 상권', 태그 없는 줄은 공통 키워드."""
    entries = []
    for line in WATCHLIST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        tag = parts[0]
        query = parts[1] if len(parts) > 1 and parts[1] else (f"{tag} 상권" if tag else "")
        if query:
            entries.append((tag, query))
    return entries


def fetch_google_rss(query: str, area_tag: str) -> list[dict]:
    url = RSS_KR.format(q=urllib.parse.quote(query))
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
                "title": title,  # 원문 그대로 — 지역 귀속은 areaTag 필드가 담당
                "source": source or "google-news",
                "url": link,
                "areaTag": area_tag,
                "publishedAt": published,
            })
    return items


def post_to_hub(items: list[dict]) -> dict:
    res = requests.post(
        f"{HUB_URL}/automation/market-news",
        json={"items": items},
        headers={"X-Webhook-Token": TOKEN},
        timeout=120,  # 적재 시 미임베딩 배치(bge-m3)까지 동기 수행 — 여유 타임아웃
    )
    res.raise_for_status()
    return res.json()


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 상권 뉴스 수집 시작", flush=True)
    total_fetched = total_saved = failures = 0
    for tag, query in load_watchlist():
        label = tag or f"공통({query})"
        try:  # 쿼리 단위 실패는 건너뛰고 계속 — cron 무인 실행 전제
            items = fetch_google_rss(query, tag)
        except Exception as e:
            print(f"{label}: 수집 실패({e})")
            failures += 1
            continue
        total_fetched += len(items)
        if dry_run:
            print(f"{label}: {len(items)}건")
            for it in items[:2]:
                print(f"  - {it['title'][:90]} ({it['source']})")
            continue
        try:
            result = post_to_hub(items)
            total_saved += result["saved"]
            print(f"{label}: {len(items)}건 → 신규 저장 {result['saved']}")
        except Exception as e:
            print(f"{label}: 허브 POST 실패 — {e}")
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
