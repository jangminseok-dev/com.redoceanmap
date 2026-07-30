"""뉴스 LLM 라벨링 — EXAONE 7.8B(Ollama)로 감성·이벤트·확신도 라벨 → 허브 적재.

허브에서 미라벨 뉴스를 받아(/automation/news-labels/pending) 라벨 후 되돌린다
(/automation/news-labels). 라벨은 학습 피처 — 정답은 실현 수익률(price_bars 조인)이 담당한다.

단일 모델 정책(2026-07-15): 프로젝트는 EXAONE 7.8B 하나만 쓴다. AWQ 2.4B 직로딩을
Ollama HTTP(exaone3.5:7.8b, 상주 서빙)로 교체 — 결과는 허브 HTTP 계약으로만 적재한다.

실행 (루트 .venv — requests만 필요):
    ../.venv/bin/python scripts/label_news.py              # 미라벨 전부(기본 상한 3000)
    ../.venv/bin/python scripts/label_news.py --limit 20   # 상한 지정
    ../.venv/bin/python scripts/label_news.py --dry-run    # 라벨 출력만, 허브 POST 안 함

백엔드 PC cron 예시(매일 02:30 — GPU 유휴 시간대):
    30 2 * * * cd /path/to/minseok && ../.venv/bin/python scripts/label_news.py >> ~/label_news.log 2>&1
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))

from core.key.secret_manager import get_secret_manager  # noqa: E402

_secrets = get_secret_manager()

HUB_URL = _secrets.get("HUB_URL", "http://localhost:8000")
TOKEN = _secrets.get("N8N_INBOUND_TOKEN")
HEADERS = {"X-Webhook-Token": TOKEN}

OLLAMA_URL = _secrets.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = "exaone3.5:7.8b"
LABELER = "exaone-7.8b"
EVENT_TYPES = ("실적", "목표가·투자의견", "신제품·기술", "규제·소송", "거시", "수급·지분", "기타")
POST_CHUNK = 200

SYSTEM = "너는 금융 뉴스 라벨러다. 반드시 JSON 한 줄로만 답한다. 설명을 덧붙이지 않는다."
PROMPT = """다음 뉴스 제목이 종목 {ticker}의 주가에 호재인지 악재인지 라벨링하라.

규칙:
- sentiment: 주가가 오를 뉴스면 양수(+), 내릴 뉴스면 음수(-), 영향 없으면 0.0. 범위 -1.0 ~ 1.0.
  주의: 부정적 단어(절벽·부족·제약)가 있어도 그것이 이 종목에 유리하면(예: 공급 부족 → 가격 상승 수혜) 호재다.
- event: 아래 7개 중 하나. '기타'는 최후의 수단이다 — 나머지 6개 중 조금이라도 해당하면 반드시 그쪽을 고른다.
  실적: 실적 발표·전망, 매출·이익, 가이던스
  목표가·투자의견: 증권사·애널리스트의 등급·목표가·밸류에이션 평가·매수/매도 추천
  신제품·기술: 신제품·수주·계약·투자·증설·데이터센터·기술 개발·특허 취득
  규제·소송: 정부·법원·경찰·노조가 개입된 사건만 — 규제·수사·소송·특허 분쟁·파업 (단순 주가 하락은 아님)
  거시: 금리·환율·업황 전반·산업 수급 (공급 부족/과잉·공급절벽 등 수급 전망 포함)
  수급·지분: 기관·유명 투자자의 매수/매도, 지분 변동·자사주·공매도·상장(IPO·ADR)
  기타: 위 어디에도 해당하지 않을 때만 (예: 단순 시세 중계, 옵션 시세표, 행사·인사 소식)
- confidence: 판단 확신도 0.0 ~ 1.0

예시:
제목: 삼성전자, 4분기 영업이익 시장 기대 상회 → {{"sentiment": 0.7, "event": "실적", "confidence": 0.9}}
제목: 모건스탠리, 애플 목표가 하향…수요 둔화 우려 → {{"sentiment": -0.6, "event": "목표가·투자의견", "confidence": 0.8}}
제목: Analyst Turns Bearish on Tesla, Cuts Rating → {{"sentiment": -0.6, "event": "목표가·투자의견", "confidence": 0.8}}
제목: 캐시 우드, 테슬라 주식 2천만 달러 추가 매수 → {{"sentiment": 0.3, "event": "수급·지분", "confidence": 0.7}}
제목: 전삼노, 파업 예고…임금 협상 결렬 → {{"sentiment": -0.4, "event": "규제·소송", "confidence": 0.8}}
제목: 메모리 공급 부족 심화…내년 D램 가격 급등 전망 → {{"sentiment": 0.7, "event": "거시", "confidence": 0.8}}
제목: 인텔 주가 오늘 6% 급락…왜? → {{"sentiment": -0.4, "event": "기타", "confidence": 0.6}}
제목: Why Micron Stock Dropped Today → {{"sentiment": -0.4, "event": "기타", "confidence": 0.6}}
제목: 엔비디아 주주총회 다음 주 개최 → {{"sentiment": 0.0, "event": "기타", "confidence": 0.6}}

제목: {title} →"""


def fetch_pending(limit: int) -> list[dict]:
    res = requests.get(
        f"{HUB_URL}/automation/news-labels/pending",
        params={"labeler": LABELER, "limit": limit},
        headers=HEADERS, timeout=30,
    )
    res.raise_for_status()
    return res.json()


def post_labels(items: list[dict]) -> int:
    saved = 0
    for start in range(0, len(items), POST_CHUNK):
        res = requests.post(
            f"{HUB_URL}/automation/news-labels",
            json={"items": items[start:start + POST_CHUNK]},
            headers=HEADERS, timeout=60,
        )
        res.raise_for_status()
        saved += res.json()["saved"]
    return saved


def parse_label(text: str) -> dict | None:
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if not match:
        return None
    try:
        raw = json.loads(match.group())
        return {
            "sentiment": round(max(-1.0, min(1.0, float(raw["sentiment"]))), 2),
            "event": raw["event"] if raw.get("event") in EVENT_TYPES else "기타",
            "confidence": round(max(0.0, min(1.0, float(raw["confidence"]))), 2),
        }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def warmup() -> None:
    """콜드 스타트 가드 — 모델 로드(디스크 캐시에 따라 수 분)를 본 라벨링과 분리한다."""
    requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": "1", "stream": False,
              "options": {"num_predict": 1}},
        timeout=600,
    ).raise_for_status()


def label_one(ticker: str, title: str) -> dict:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": PROMPT.format(
                ticker=ticker, title=title, events=" | ".join(EVENT_TYPES))},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "num_predict": 64, "num_ctx": 2048},
    }
    for attempt in (1, 2):  # 일시 장애(모델 재로드·Ollama 재시작)는 1회 재시도
        try:
            # 600초 — 뉴스 수집(bge-m3)과 겹치면 Ollama가 EXAONE을 내렸다 다시 올린다(RAM 7.7GB)
            res = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=600)
            break
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt == 2:
                raise
    res.raise_for_status()
    text = res.json()["message"]["content"]
    # 파싱 실패는 중립·확신도 0으로 저장 — 미라벨로 남기면 매 실행 같은 건에서 재실패(수렴 불가)
    return parse_label(text) or {"sentiment": 0.0, "event": "기타", "confidence": 0.0}


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 3000
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 라벨링 시작 (labeler={LABELER})", flush=True)

    pending = fetch_pending(limit)
    if not pending:
        print("미라벨 뉴스 없음 — 종료", flush=True)
        return 0
    print(f"미라벨 {len(pending)}건 — Ollama({OLLAMA_MODEL}) 웜업 후 라벨링 시작", flush=True)
    warmup()

    # 200건 단위 즉시 저장 — 중간 크래시에도 저장분은 남고, 미라벨 큐라 재실행이 이어받는다.
    items, labeled, parse_failed, saved = [], 0, 0, 0
    for n, news in enumerate(pending, 1):
        label = label_one(news["ticker"], news["title"])
        if label["confidence"] == 0.0 and label["event"] == "기타":
            parse_failed += 1
        labeled += 1
        items.append({
            "newsId": news["newsId"],
            "labeler": LABELER,
            "sentiment": label["sentiment"],
            "eventType": label["event"],
            "confidence": label["confidence"],
        })
        if not dry_run and len(items) >= POST_CHUNK:
            saved += post_labels(items)
            items = []
        if dry_run and n <= 10:
            print(f"  [{news['ticker']}] {news['title'][:50]} → {label}", flush=True)
        if n % 100 == 0:
            print(f"  진행 {n}/{len(pending)} (누적 저장 {saved})", flush=True)

    if dry_run:
        print(f"[dry-run] 라벨 {labeled}건 생성 (파싱 실패 {parse_failed}) — POST 생략", flush=True)
        return 1 if parse_failed else 0
    if items:
        saved += post_labels(items)
    print(
        f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 합계: 라벨 {labeled}건 "
        f"(파싱 실패 {parse_failed}) / 신규 저장 {saved}건",
        flush=True,
    )
    # 파싱 실패는 중립으로 저장돼 데이터는 남지만 모델이 형식을 못 지킨 것 — 실패로 센다.
    # Ollama 자체 장애는 label_one이 재시도 후 예외를 전파해 이미 비정상 종료한다.
    return 1 if parse_failed else 0


if __name__ == "__main__":
    # 부분 실패도 종료코드 1 — cron·감시가 실패를 관측할 수 있어야 한다.
    sys.exit(main())
