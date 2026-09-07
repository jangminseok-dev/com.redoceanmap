"""수집 신선도 감시 — 데이터가 조용히 멈춘 것을 잡아 이메일로 알린다.

배경: 2026-07-25~27 백엔드 PC가 2일 6시간 꺼져 cron 7종이 전부 멈췄는데 **아무도 몰랐다.**
어드민 `/admin/data-sources`에 신선도 배지가 있지만 사람이 열어야 보인다. 이 스크립트는
같은 판정 정책(`admin/domain/services/dataset_freshness` — 순수 모듈)을 재사용해
능동적으로 알린다. 임계값을 두 곳에 적지 않기 위해 정책은 import하고 배관만 여기서 한다.

**한계(중요): 이 감시는 백엔드 PC 안에서 돈다 — PC가 통째로 꺼지면 이것도 함께 죽는다.**
호스트 다운은 밖에서 `/health`를 폴링하는 외부 업타임 모니터만 잡는다(그 용도로 `/health`를
DB·Redis 확인형으로 만들어 뒀다). 이 스크립트가 잡는 것은 "호스트는 살아 있는데 특정
수집만 멈춘" 경우다.

발송은 n8n 웹훅 경유다(Gmail 자격증명은 n8n이 보유 — 백엔드에 비밀이 없다,
`chat/adapter/outbound/gateways/email_composer_gateway.py`와 같은 창구).
알림 상태를 저장하지 않으므로 장애가 이어지면 실행 주기마다 한 통씩 온다(일 1회 cron 전제).

실행 (백엔드 이미지 파드 — 호스트 cron venv에는 sqlalchemy가 없다). 스케줄과 기대 커밋 판독은
infra/k8s/overlays/prod/cronjobs/check-freshness.yaml(매일 09:00, .git에서 HEAD를 읽어 --expect-commit으로 넘긴다):
    kubectl -n redocean create job --from=cronjob/check-freshness check-freshness-manual-$(date +%s)
    kubectl -n redocean exec deploy/backend -- python scripts/check_freshness.py --dry-run  # 발송 생략(실행 중 파드에서)

배포 드리프트까지 보려면 기대 커밋을 넘긴다(컨테이너 안에는 git이 없다):
    kubectl -n redocean exec deploy/backend -- python scripts/check_freshness.py \
        --expect-commit "$(git -C /home/host/projects/com.redoceanmap rev-parse --short HEAD)"
"""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))
from admin.domain.services.dataset_freshness import FreshnessState, evaluate  # noqa: E402
from core.key.secret_manager import get_secret_manager  # noqa: E402

_secrets = get_secret_manager()

# (판정 키, 표시명, 테이블, market 전용 DB인가)
# 판정 키는 dataset_freshness.SCHEDULES의 키와 같아야 한다 — 다르면 UNSCHEDULED로 조용히 빠진다.
DATASETS = [
    ("news_articles", "종목 뉴스", "news_articles", False),
    ("news_labels", "뉴스 라벨", "news_labels", False),
    ("price_bars", "주가 봉(OHLCV)", "price_bars", False),
    ("forecast_snapshots", "예측 스냅샷", "forecast_snapshots", False),
    ("fundamental_snapshots", "펀더멘털 스냅샷", "fundamental_snapshots", False),
    ("market_news", "상권 뉴스", "market_news_articles", True),
    ("business_permits", "인허가 업소", "business_permits", True),
]

# 알릴 상태. FRESH·UNSCHEDULED는 정상이므로 뺀다.
ALERT_STATES = {FreshnessState.LATE, FreshnessState.STALE, FreshnessState.UNKNOWN}

STATE_LABEL = {
    FreshnessState.LATE: "지연",
    FreshnessState.STALE: "정지",
    FreshnessState.UNKNOWN: "적재 이력 없음",
}


def _driver(url: str) -> str:
    # 다른 배치와 같은 규칙 — 접두사가 빠지면 psycopg2를 찾다가 죽는다(2026-07-27 회귀).
    return url.replace("postgresql://", "postgresql+psycopg://")


def shared_url() -> str:
    return _driver(_secrets.require("DATABASE_URL"))


def market_url() -> str:
    return _driver(_secrets.get("MARKET_DATABASE_URL") or _secrets.require("DATABASE_URL"))


def latest_loaded_at(engine, table: str) -> datetime | None:
    """적재 시각의 최댓값. 도메인 시각(ts·as_of·published_at)이 아니라 created_at이다 —
    수집이 멈춰도 도메인 시각은 최신으로 보인다(2026-07-27 감지 실패의 원인)."""
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT max(created_at) FROM {table}")).scalar()


# 배포 드리프트 — "호스트도 살아 있고 수집도 도는데 코드만 낡은" 경우.
# 2026-08-20: 이미지가 12일 낡아 /chat/ask/progress가 404였는데 위 데이터셋 감시는
# 정상이었다(수집은 멈추지 않았다). 상태 감시와 버전 감시는 다른 축이다.
#
# 기대 커밋은 호스트 git만 안다(컨테이너에 .git이 없다) — cron이 --expect-commit으로 넘긴다.
# 유예를 두는 이유: 커밋 직후 아직 배포 전인 정상 상태를 매일 알리면 알림이 무뎌진다.
DEPLOY_DRIFT_GRACE = timedelta(days=3)


def _built_at() -> datetime | None:
    """이미지에 구운 빌드 시각. 굽지 않은 이미지는 파싱 불가 → None."""
    raw = _secrets.get("BUILT_AT", "unknown")
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def deploy_drift(expect_commit: str | None, now: datetime) -> str | None:
    """배포 커밋이 기대와 다르고 유예를 넘겼으면 사유 문자열, 아니면 None."""
    if not expect_commit:
        return None
    running = _secrets.get("GIT_SHA", "unknown")
    if running == "unknown":
        return None  # --build-arg 없이 만든 이미지 — 대조할 값 자체가 없다
    # 길이가 다른 축약형끼리도 맞도록 접두사로 비교한다
    if running.startswith(expect_commit) or expect_commit.startswith(running):
        return None

    built = _built_at()
    if built is None:
        return f"배포 커밋 불일치 — 실행 중 {running}, 저장소 {expect_commit} (빌드 시각 불명)"
    age = now - built
    if age < DEPLOY_DRIFT_GRACE:
        return None  # 방금 커밋했고 아직 배포 전 — 정상
    return (
        f"배포 커밋 불일치 {age.days}일째 — 실행 중 {running}"
        f"(빌드 {built:%Y-%m-%d}), 저장소 {expect_commit}"
    )


def collect_verdicts() -> list[tuple[str, str, object]]:
    """(표시명, 상태 라벨, 판정) 목록. DB 접속 자체가 실패하면 예외를 그대로 올린다."""
    now = datetime.now(UTC)
    shared = create_engine(shared_url(), pool_pre_ping=True)
    market = create_engine(market_url(), pool_pre_ping=True)
    rows = []
    try:
        for key, name, table, is_market in DATASETS:
            engine = market if is_market else shared
            verdict = evaluate(key, latest_loaded_at(engine, table), now)
            rows.append((name, verdict.state, verdict))
    finally:
        shared.dispose()
        market.dispose()
    return rows


def build_body(problems: list[tuple[str, str, object]], drift: str | None = None) -> str:
    lines = []
    if problems:
        lines += ["다음 수집이 기대 주기를 넘겼습니다.", ""]
    for name, state, verdict in problems:
        age = "적재 이력 없음" if verdict.age_seconds is None else f"{verdict.age_seconds // 3600}시간 경과"
        lines.append(f"  · {name} — {STATE_LABEL[state]} (기대 주기: {verdict.expected}, {age})")
    if drift:
        lines += ["", "배포가 저장소보다 뒤처져 있습니다.", "", f"  · {drift}",
                  "    조치: 백엔드 PC에서 infra/deploy.sh"]
    lines += [
        "",
        "확인: 어드민 → 데이터소스, 그리고 백엔드 PC의 cron 로그(~/collect_*.log).",
        "이 메일은 백엔드 PC 안에서 도는 감시가 보냅니다 — PC가 꺼지면 이 메일도 오지 않습니다.",
    ]
    return "\n".join(lines)


def send(subject: str, body: str) -> None:
    to = _secrets.get("ALERT_EMAIL")
    if not to:
        raise RuntimeError("ALERT_EMAIL 미설정 — .env에 수신 주소를 넣어야 알림이 나갑니다.")
    res = requests.post(
        _secrets.require("N8N_EMAIL_WEBHOOK_URL"),
        json={"to": to, "subject": subject, "body": body},
        headers={"X-Webhook-Token": _secrets.get("N8N_OUTBOUND_TOKEN", "")},
        timeout=30,
    )
    res.raise_for_status()


def _arg_value(flag: str) -> str | None:
    if flag not in sys.argv:
        return None
    idx = sys.argv.index(flag) + 1
    return sys.argv[idx] if idx < len(sys.argv) else None


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    stamp = f"[{datetime.now():%Y-%m-%d %H:%M:%S}]"

    rows = collect_verdicts()
    for name, state, verdict in rows:
        print(f"  {name}: {state.value}" + (f" ({verdict.age_seconds // 3600}시간)"
                                            if verdict.age_seconds is not None else ""))

    drift = deploy_drift(_arg_value("--expect-commit"), datetime.now(UTC))
    print(f"  배포: {drift or '기대 커밋과 일치(또는 대조 생략)'}")

    problems = [r for r in rows if r[1] in ALERT_STATES]
    if not problems and not drift:
        print(f"{stamp} 전 데이터셋·배포 정상 — 알림 없음", flush=True)
        return 0

    parts = ([f"수집 지연·정지 {len(problems)}건"] if problems else []) + (["배포 드리프트"] if drift else [])
    subject = f"[redoceanmap] {' / '.join(parts)}"
    body = build_body(problems, drift)
    print(f"{stamp} 이상 감지\n{body}", flush=True)
    if dry_run:
        print("[dry-run] 메일 발송 생략", flush=True)
        return 1
    send(subject, body)
    print(f"{stamp} 알림 발송 완료", flush=True)
    return 1


if __name__ == "__main__":
    # 이상이 있으면 종료코드 1 — 수집 스크립트와 같은 규약이다.
    sys.exit(main())
