"""모의투자 리플레이 — 2026-07-30(스냅샷 signal_config 스탬프 시작)부터 어제까지 step을 날짜 순으로 부른다.

허브 HTTP 계약만 쓴다(snapshot_forecasts.py와 같은 방식). 각 날짜의 as_of는 14:00 KST(05:00 UTC)로,
실 cron과 같은 시각이다. 스냅샷이 없는 날(휴장)은 서버가 skip을 돌려준다. 재실행은 멱등이다.

    python scripts/replay_paper.py                      # 7/30 ~ 어제
    python scripts/replay_paper.py 2026-08-01 2026-08-10  # 구간 지정
"""
import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.key.secret_manager import get_secret_manager  # noqa: E402

_secrets = get_secret_manager()
HUB_URL = _secrets.get("HUB_URL", "http://localhost:8000")
HEADERS = {"X-Webhook-Token": _secrets.get("N8N_INBOUND_TOKEN")}
START_DEFAULT = date(2026, 7, 30)
AS_OF_UTC = time(5, 0)  # 14:00 KST


def main() -> int:
    start = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else START_DEFAULT
    end = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else datetime.now(UTC).date() - timedelta(days=1)
    day, failures = start, 0
    while day <= end:
        as_of = datetime.combine(day, AS_OF_UTC, tzinfo=UTC)
        try:
            res = requests.post(f"{HUB_URL}/automation/paper/step",
                                json={"as_of": as_of.isoformat(), "replay": True}, headers=HEADERS, timeout=1800)
            res.raise_for_status()
            b = res.json()
            print(f"{day} 체결 {b['filled']} 판단 {b['decisions']} 채점 {b['scored']} 평가 {b['equity_rows']}"
                  + (f" — {b['skipped']}" if b.get("skipped") else ""), flush=True)
        except requests.RequestException as e:
            print(f"{day} 실패: {e}", flush=True)
            failures += 1
        day += timedelta(days=1)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
