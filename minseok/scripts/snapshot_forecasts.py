"""예측 스냅샷 캡처·채점 — 허브 /automation/forecast-snapshots 호출.

워치리스트(collect_news와 공유) 전 종목의 forecast(방향·확률·신호 분해)를 매일 1회
DB에 동결하고, horizon(5·20거래일)이 도래한 과거 스냅샷을 실현 수익률로 채점한다.
스포크를 직접 만지지 않고 허브 HTTP 계약만 호출한다 — 중복은 서버
((ticker, horizon_days, as_of) 유니크)가 걸러내므로 주말/재실행은 자연 스킵(자가치유).

계산은 서버가 한다(종목당 워크포워드 수 초) — 서버 부하·타임아웃 분산을 위해
20종목 단위 배치로 나눠 POST하고, 배치 실패는 로그 후 계속한다(부분 실패 격리).

실행:
    python scripts/snapshot_forecasts.py            # 캡처 + 채점
    python scripts/snapshot_forecasts.py --dry-run  # 대상 티커 출력만 (허브 불요)

백엔드 PC cron(매일 14:00 KST — **일봉 적재 시각에 맞춘 것**, 2026-07-23 변경):
    0 14 * * * cd /path/to/minseok && ../venv/bin/python scripts/snapshot_forecasts.py >> ~/snapshot_forecasts.log 2>&1

세션 D의 일봉은 D+1 13:05 KST에 들어온다. 이전 07:30은 그보다 6시간 일러 매일 한 세션
묵은 봉으로 as_of가 잡혔다(보드가 "기준 7/21"인데 가격은 7/22인 화면의 원인).
장 마감 시각이 아니라 **저장 일봉이 도착한 뒤**가 기준이다 — 캡처는 DB 봉만 읽는다
(market_data=None으로 라이브 폴백 차단).
"""

import sys
from datetime import datetime
from pathlib import Path

import requests

from collect_news import load_watchlist

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))

from core.key.secret_manager import get_secret_manager  # noqa: E402

_secrets = get_secret_manager()

HUB_URL = _secrets.get("HUB_URL", "http://localhost:8000")
TOKEN = _secrets.get("N8N_INBOUND_TOKEN")
HEADERS = {"X-Webhook-Token": TOKEN}

HORIZONS = [5, 20]   # 단기(1주) + 스윙(1개월) — 두 지평 모두 채점 데이터 축적
BATCH_SIZE = 20      # 요청당 티커 수 — 서버 계산 시간 상한(배치당 1~2분)
TIMEOUT = 1800


def capture(tickers: list[str]) -> tuple[int, list[str]]:
    captured, skipped = 0, []
    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i:i + BATCH_SIZE]
        try:
            res = requests.post(
                f"{HUB_URL}/automation/forecast-snapshots",
                json={"tickers": batch, "horizons": HORIZONS},
                headers=HEADERS, timeout=TIMEOUT,
            )
            res.raise_for_status()
            body = res.json()
            captured += body["captured"]
            skipped.extend(body["skipped"])
        except requests.RequestException as e:
            print(f"  [경고] 배치 실패({batch[0]}~{batch[-1]}): {e} — 다음 배치 계속")
    return captured, skipped


def score() -> tuple[int, int]:
    res = requests.post(
        f"{HUB_URL}/automation/forecast-snapshots/score", headers=HEADERS, timeout=TIMEOUT,
    )
    res.raise_for_status()
    body = res.json()
    return body["scored"], body["pending"]


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    tickers = [ticker for _, ticker, _ in load_watchlist() if ticker]
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] 대상 {len(tickers)}종목 × horizons {HORIZONS}")
    if dry_run:
        print(" ".join(tickers))
        return

    captured, skipped = capture(tickers)
    print(f"캡처: 신규 {captured}건, skip {len(skipped)}티커"
          + (f" ({', '.join(skipped[:10])}{'…' if len(skipped) > 10 else ''})" if skipped else ""))

    scored, pending = score()
    print(f"채점: {scored}건 완료, {pending}건 대기(horizon 미도래)")


if __name__ == "__main__":
    main()
