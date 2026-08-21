"""판정 가중치 재적합 — 허브 /automation/forecast-refit 호출.

채점 완료된 예측 스냅샷(동결 원신호 × 실현 수익률)으로 후보 조합 ~32개를 재채점하고,
통계 게이트(n≥100 + Wilson 하한 > 기준선 + 현행 대비 마진 0.02) 통과 시 활성 판정 조합을
자동 교체한다. 게이트 미달이어도 리포트는 저장된다(표본 축적 경과 관측 —
어드민 /admin/forecast-refit). 계산은 서버가 한다(표본 전량 × 32조합, 수 초).

실행:
    python scripts/refit_forecast_weights.py            # 재적합 + 게이트 통과 시 승격
    python scripts/refit_forecast_weights.py --dry-run  # 리더보드 계산·리포트 저장까지(승격만 생략)

백엔드 PC cron(매주 토 15:00 KST — 금요 세션 채점 cron 14:00 직후):
    0 15 * * 6 cd /path/to/minseok && ../venv/bin/python scripts/refit_forecast_weights.py >> ~/refit_forecast_weights.log 2>&1

현재 표본(UP 판정 n<100)으로는 당분간 "게이트 미달" 리포트만 쌓이는 것이 정상이다 —
표본이 차는 시점(~2026-09)부터 승격이 실제로 발화한다.
"""

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
TIMEOUT = 600


def main() -> int:
    promote = "--dry-run" not in sys.argv
    print(f"[{datetime.now():%Y-%m-%d %H:%M}] 재적합 시작 (promote={promote})")
    try:
        res = requests.post(
            f"{HUB_URL}/automation/forecast-refit",
            json={"promote": promote}, headers=HEADERS, timeout=TIMEOUT,
        )
        res.raise_for_status()
    except requests.RequestException as e:
        print(f"[오류] 재적합 요청 실패: {e}")
        return 1
    body = res.json()
    print(f"승격: {body['promoted']}"
          + (f" → 활성 조합 {body['activated_key']}" if body.get("activated_key") else ""))
    for reason in body.get("reasons", []):
        print(f"  - {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
