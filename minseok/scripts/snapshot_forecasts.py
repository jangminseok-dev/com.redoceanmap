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
from datetime import UTC, datetime, time
from time import sleep   # datetime.time과 이름이 겹쳐 모듈을 통째로 들이지 않는다
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
# 모의투자 step의 as_of = 캡처 봉 기준일 + 05:00 UTC(14:00 KST). replay_paper.py의 AS_OF_UTC와 같은 규약 —
# 판단 시각이 아니라 "어느 세션 종가를 보고 낸 판단인가"의 날짜 라벨이다. 14:00 실행의 최신 봉은 항상
# 전날 세션이라, 지금 시각을 쓰면 step이 "오늘" 스냅샷을 찾다 매일 휴장일 skip이 된다(2026-09-09 사고).
STEP_AS_OF_UTC = time(5, 0)
BATCH_SIZE = 20      # 요청당 티커 수 — 서버 계산 시간 상한(배치당 1~2분)
TIMEOUT = 1800


def _post(path: str, body: dict, attempts: int = 6):
    """허브 호출 — 연결 거부·5xx면 지수 대기 후 재시도(최대 ~5분).

    호스트 cron이 k3s 백엔드를 localhost로 부르는데, 매일 00:10 자동 재부팅·배포 창에 연결이 거부되면
    실행이 통째로 죽었다(2026-09-17 스냅샷·모의투자 세션 누락). 캡처·채점·step 모두 멱등이라 재시도가 안전하다.
    """
    for attempt in range(attempts):
        try:
            res = requests.post(f"{HUB_URL}{path}", json=body, headers=HEADERS, timeout=TIMEOUT)
            if res.status_code < 500:
                res.raise_for_status()
                return res
        except requests.ConnectionError:
            if attempt == attempts - 1:
                raise
        wait = 10 * 2 ** attempt
        print(f"  허브 연결 실패 — {wait}초 뒤 재시도({attempt + 1}/{attempts}) {path}", flush=True)
        sleep(wait)
    res.raise_for_status()
    return res


def capture(tickers: list[str]) -> tuple[int, list[str], int, datetime | None]:
    captured, skipped, failed_batches = 0, [], 0
    bar_as_of: datetime | None = None  # 배치들이 본 최신 봉 기준일 — step의 날짜 축
    for i in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[i:i + BATCH_SIZE]
        try:
            res = _post("/automation/forecast-snapshots", {"tickers": batch, "horizons": HORIZONS})
            body = res.json()
            captured += body["captured"]
            skipped.extend(body["skipped"])
            if body.get("as_of"):
                seen = datetime.fromisoformat(body["as_of"])
                bar_as_of = seen if bar_as_of is None or seen > bar_as_of else bar_as_of
        except requests.RequestException as e:
            print(f"  [경고] 배치 실패({batch[0]}~{batch[-1]}): {e} — 다음 배치 계속")
            failed_batches += 1
    return captured, skipped, failed_batches, bar_as_of


def score() -> tuple[int, int]:
    res = _post("/automation/forecast-snapshots/score", {})
    body = res.json()
    return body["scored"], body["pending"]


def paper_step(bar_as_of: datetime) -> dict:
    """모의투자 일일 step — 스냅샷 캡처·채점 **뒤**에 돈다(판단이 방금 캡처한 스냅샷을 읽어야 한다).

    as_of는 캡처 봉 기준일의 05:00 UTC로 고정한다 — 스냅샷 조회(snapshots_on)·뉴스 컷오프·
    다음 세션 시가 체결(bars_after)이 리플레이와 같은 축이 되고, 같은 날 재실행은 (계정, as_of)
    유니크로 멱등하다.
    """
    as_of = datetime.combine(bar_as_of.date(), STEP_AS_OF_UTC, tzinfo=UTC)
    res = _post("/automation/paper/step", {"as_of": as_of.isoformat()})
    return res.json()


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    tickers = [ticker for _, ticker, _ in load_watchlist() if ticker]
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] 대상 {len(tickers)}종목 × horizons {HORIZONS}")
    if dry_run:
        print(" ".join(tickers))
        return 0

    captured, skipped, failed_batches, bar_as_of = capture(tickers)
    print(f"캡처: 신규 {captured}건, skip {len(skipped)}티커"
          + (f" ({', '.join(skipped[:10])}{'…' if len(skipped) > 10 else ''})" if skipped else "")
          + (f" / 배치 실패 {failed_batches}건" if failed_batches else ""))

    scored, pending = score()
    print(f"채점: {scored}건 완료, {pending}건 대기(horizon 미도래)")

    if bar_as_of is None:
        print("  [경고] 캡처 응답에 봉 기준일이 없어 모의투자 step을 건너뜁니다 — 다음 실행에서 자연 재시도")
        return 1
    try:
        step = paper_step(bar_as_of)
        print(f"모의투자 step(기준 {bar_as_of:%Y-%m-%d}): 체결 {step['filled']} · 판단 {step['decisions']}"
              f" · 채점 {step['scored']}" + (f" · skip({step['skipped']})" if step.get("skipped") else ""))
    except requests.RequestException as e:
        print(f"  [경고] 모의투자 step 실패: {e} — 다음 실행에서 자연 재시도(멱등)")
        failed_batches += 1
    return 1 if failed_batches else 0


if __name__ == "__main__":
    # 부분 실패도 종료코드 1 — cron·감시가 실패를 관측할 수 있어야 한다.
    sys.exit(main())
