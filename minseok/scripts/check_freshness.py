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

import math
import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import requests
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))
from admin.domain.services.dataset_freshness import FreshnessState, evaluate  # noqa: E402
from core.key.secret_manager import get_secret_manager  # noqa: E402
from stock.domain.value_objects.backtest_report import hit_unit, is_up_hit  # noqa: E402

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


# 모의투자 step 누락 — 위 DATASETS(적재 시각 나이)로는 못 잡는다. step은 거래 세션마다 한 번이라
# 주말 3일 공백이 정상이고, 2026-09-12~14 PC 다운처럼 한 세션만 빠지면 나이가 임계값에 닿지 않는다.
# 그래서 SPY 일봉을 세션 달력으로 삼아 "판단 예정 시각이 지났는데 판단이 없는 세션"을 센다.
# 세션 D(미국 날짜)의 step은 D+1일 14:00 KST(05:00 UTC, snapshot_forecasts cron)에 돌고 약 1시간 걸린다.
PAPER_CALENDAR_TICKER = "SPY"
PAPER_STEP_DUE = timedelta(days=1, hours=7)  # 세션 날짜 00:00 UTC 기준 — D+1일 16:00 KST


def overdue_paper_sessions(session_dates: list[date], last_decision: date, now: datetime) -> list[date]:
    """마지막 라이브 판단 이후 세션 중 step 예정 시각이 지난 것. 순수 함수(now 주입)."""
    return sorted(d for d in session_dates
                  if d > last_decision and datetime.combine(d, time(0), tzinfo=UTC) + PAPER_STEP_DUE <= now)


def paper_lag(engine, now: datetime) -> str | None:
    """누락 세션이 있으면 사유 문자열, 아니면 None."""
    with engine.connect() as conn:
        last = conn.execute(text("SELECT max(as_of) FROM paper_decisions WHERE NOT replayed")).scalar()
        if last is None:
            return None  # 라이브 운용 전
        sessions = conn.execute(
            text("SELECT ts FROM price_bars WHERE ticker = :t AND timeframe = '1d' AND ts > :last"),
            {"t": PAPER_CALENDAR_TICKER, "last": last},
        ).scalars().all()
    # SPY 일봉 ts는 미국 날짜 00:00 ET(04~05:00 UTC)라 UTC 날짜가 곧 세션 날짜다
    overdue = overdue_paper_sessions([ts.astimezone(UTC).date() for ts in sessions], last.date(), now)
    if not overdue:
        return None
    return (f"AI 모의투자 판단 누락 {len(overdue)}세션 — 마지막 판단 기준일 {last:%Y-%m-%d}, "
            f"빠진 세션 {', '.join(f'{d:%m/%d}' for d in overdue)}")


# 신호 성적 감시(2026-09-17) — 9/1 승격 조합의 반등(UP) 신호가 9월에 적중 17.8%(기준선 25%)로 무너졌는데
# 2주 넘게 아무도 몰랐다. 매일 최근 SIGNAL_WINDOW_DAYS일 채점분을 실효 표본(종목×ISO 주 군집)으로 세어
# 종목 기준선 아래면 알린다. 적중 정의는 백테스트·재적합·스냅샷 채점과 같은 is_up_hit(변동성 초과).
SIGNAL_WINDOW_DAYS = 14
# 2026-09-18 개정: ① 활성 조합만 경보(내린 조합의 성적은 연구 기록이지 장애가 아니다)
# ② "적중률 ≤ 기준선"이 아니라 **95% 신뢰구간 상한이 기준선 아래**일 때만 — 9/18 헛경보는 1/19군집(구간 1~26%)으로
# 기준선 25.6%와 구별되지 않는데 매일 메일을 보냈다. 군집 하한도 15 → 30으로 올린다.
SIGNAL_MIN_EFFECTIVE = 30  # 군집이 이보다 적으면 판단하지 않는다(잡음)


def _wilson_upper(rate: float, n: int, z: float = 1.96) -> float:
    """실효 표본 n에서 관측 비율의 95% Wilson 상한 — 표본이 작으면 1에 가까워 경보가 울리지 않는다."""
    if n <= 0:
        return 1.0
    den = 1 + z * z / n
    ctr = (rate + z * z / (2 * n)) / den
    return ctr + z * math.sqrt(rate * (1 - rate) / n + z * z / (4 * n * n)) / den


def signal_decay_verdict(recent: list[tuple], history: list[tuple], active_config: str | None = None) -> str | None:
    """recent·history: (ticker, as_of, direction, realized_return_pct, atr_pct, signal_config). 순수 함수.

    history(전 기간 채점분)로 종목 기준선(변동성 초과 상승 비율)을 만들고, recent의 UP 신호를 **판정 조합별로**
    군집 평균해 그 군집들의 기준선 평균과 비교한다 — 창에 옛 조합의 잘 맞은 신호가 섞이면 새 조합의 부진이
    평균에 묻힌다(9/17 실측: 8/27~31 옛 조합 49건이 9월 부진 45건을 가렸다).

    2026-09-18 개정: **활성 조합만** 판정하고(내린 조합은 이미 쓰지 않는다), 적중률의 95% 상한이 기준선 아래일
    때만 사유를 낸다 — 9/18 헛경보(1/19군집)는 통계적으로 기준선과 구별되지 않았다. active_config가 None이면
    (조회 실패·미설정) 아무것도 판정하지 않는다.
    """
    if active_config is None:
        return None
    base: dict[str, list[bool]] = {}
    for ticker, _as_of, _d, ret, atr, _cfg in history:
        base.setdefault(ticker, []).append(is_up_hit(ret, hit_unit(atr, 5)))
    by_config: dict[str, dict[tuple, list[bool]]] = {}
    for ticker, as_of, direction, ret, atr, cfg in recent:
        if direction != "UP" or ticker not in base:
            continue
        year, week, _ = as_of.isocalendar()
        by_config.setdefault(cfg or "(조합 미기록)", {}).setdefault((ticker, year, week), []).append(
            is_up_hit(ret, hit_unit(atr, 5)))
    reasons = []
    for cfg, clusters in sorted(by_config.items()):
        if cfg != active_config:
            continue
        n = len(clusters)
        if n < SIGNAL_MIN_EFFECTIVE:
            continue
        rate = sum(sum(h) / len(h) for h in clusters.values()) / n
        baseline = sum(sum(base[k[0]]) / len(base[k[0]]) for k in clusters) / n
        upper = _wilson_upper(rate, n)
        if upper < baseline:
            reasons.append(f"{cfg} 반등 신호 적중 {rate:.1%}(95% 상한 {upper:.1%}) < 종목 기준선 {baseline:.1%}"
                           f" (실효 표본 {n}군집)")
    if not reasons:
        return None
    return f"최근 {SIGNAL_WINDOW_DAYS}일 채점분에서 " + "; ".join(reasons) + " — 신호가 평소보다 못 맞히고 있습니다"


RISK_REPORT_MAX_AGE_DAYS = 10   # 주 1회 배치(토 06:00) — 이보다 오래되면 보드 수치가 낡은 것이다


def risk_signal_verdict(latest: tuple[datetime, dict] | None, previous: dict | None, now: datetime) -> str | None:
    """위험 신호 보드가 보여 주는 신호가 아직 검증되는가 — 화면이 조용히 수치를 내리는 것만으로는 아무도 모른다.

    ① 검증되던 신호가 이번 주 검증에서 떨어졌으면 사유(보드는 자동으로 수치를 내리지만 사람은 알아야 한다)
    ② 리포트 자체가 낡았으면(주간 배치 미실행) 사유
    2026-09-18 신설 — 방향 신호 경보를 활성 조합으로 좁힌 자리에, 실제로 사용자에게 보이는 신호를 감시한다.
    """
    if latest is None:
        return "위험 신호 검증 리포트가 없습니다 — scripts/backtest_risk_signal.py 실행 필요"
    ran_at, payload = latest
    age_days = (now - ran_at).total_seconds() / 86400
    if age_days > RISK_REPORT_MAX_AGE_DAYS:
        return (f"위험 신호 검증 리포트가 {age_days:.0f}일 지났습니다(주 1회 기대)"
                " — CronJob backtest-risk-signal 확인 필요")
    dropped = []
    prev_valid = {s["key"] for s in (previous or {}).get("signals", ()) if s.get("validated")}
    for s in payload.get("signals", ()):
        if s["key"] in prev_valid and not s.get("validated"):
            test = s.get("test", {})
            dropped.append(f"{s['label']} — 검증 구간 {test.get('rate', 0):.1%} vs 기준 {test.get('base', 0):.1%}"
                           f"(전주까지 검증됨, 실효 표본 {test.get('n_eff', 0):,.0f})")
    if dropped:
        return "위험 신호가 검증에서 떨어졌습니다: " + "; ".join(dropped)
    return None


def risk_signal_decay(engine, now: datetime) -> str | None:
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT ran_at, payload FROM risk_signal_reports ORDER BY ran_at DESC LIMIT 2"
        )).all()
    latest = (rows[0][0], rows[0][1]) if rows else None
    previous = rows[1][1] if len(rows) > 1 else None
    return risk_signal_verdict(latest, previous, now)


def signal_decay(engine, now: datetime) -> str | None:
    cols = "ticker, as_of, direction, realized_return_pct, atr_pct, signal_config"
    with engine.connect() as conn:
        active = conn.execute(text(
            "SELECT config_key FROM forecast_signal_configs WHERE is_active LIMIT 1"
        )).scalar()
        recent = conn.execute(text(
            f"SELECT {cols} FROM forecast_snapshots WHERE horizon_days = 5 AND realized_return_pct IS NOT NULL"
            " AND NOT earnings_veto AND as_of >= :since"
        ), {"since": now - timedelta(days=SIGNAL_WINDOW_DAYS + 7)}).all()  # 5거래일 채점 지연만큼 창을 늘린다
        history = conn.execute(text(
            f"SELECT {cols} FROM forecast_snapshots WHERE horizon_days = 5 AND realized_return_pct IS NOT NULL"
            " AND NOT earnings_veto"
        )).all()
    return signal_decay_verdict([tuple(r) for r in recent], [tuple(r) for r in history], active)


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


def build_body(problems: list[tuple[str, str, object]], drift: str | None = None,
               paper: str | None = None, signal: str | None = None, risk: str | None = None) -> str:
    lines = []
    if problems:
        lines += ["다음 수집이 기대 주기를 넘겼습니다.", ""]
    for name, state, verdict in problems:
        age = "적재 이력 없음" if verdict.age_seconds is None else f"{verdict.age_seconds // 3600}시간 경과"
        lines.append(f"  · {name} — {STATE_LABEL[state]} (기대 주기: {verdict.expected}, {age})")
    if paper:
        lines += ["", "모의투자 일일 step이 돌지 않았습니다.", "", f"  · {paper}",
                  "    조치: 백엔드 PC에서 minseok/ 기준 ../venv/bin/python scripts/snapshot_forecasts.py (멱등)"]
    if signal:
        lines += ["", "주식 신호 성적이 기준선 아래입니다.", "", f"  · {signal}",
                  "    조치: 어드민 → 예측 재적합에서 조합별 최근 성적 확인 · 활성 조합 교체 여부 판단(자동 승격은 꺼져 있음)"]
    if risk:
        lines += ["", "위험 신호 보드의 검증 상태가 바뀌었습니다.", "", f"  · {risk}",
                  "    조치: 보드는 검증 미달 신호의 수치를 자동으로 내립니다 — 어떤 신호를 계속 보여줄지 판단 필요"]
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

    engine = create_engine(shared_url(), pool_pre_ping=True)
    try:
        paper = paper_lag(engine, datetime.now(UTC))
        signal = signal_decay(engine, datetime.now(UTC))
        risk = risk_signal_decay(engine, datetime.now(UTC))
    finally:
        engine.dispose()
    print(f"  모의투자: {paper or '누락 세션 없음'}")
    print(f"  신호 성적: {signal or '기준선 이상(또는 표본 부족)'}")
    print(f"  위험 신호: {risk or '검증 유지'}")

    problems = [r for r in rows if r[1] in ALERT_STATES]
    if not problems and not drift and not paper and not signal and not risk:
        print(f"{stamp} 전 데이터셋·배포·모의투자·신호 성적 정상 — 알림 없음", flush=True)
        return 0

    parts = (([f"수집 지연·정지 {len(problems)}건"] if problems else []) + (["배포 드리프트"] if drift else [])
             + (["모의투자 step 누락"] if paper else []) + (["신호 성적 저하"] if signal else [])
             + (["위험 신호 검증 이탈"] if risk else []))
    subject = f"[redoceanmap] {' / '.join(parts)}"
    body = build_body(problems, drift, paper, signal, risk)
    print(f"{stamp} 이상 감지\n{body}", flush=True)
    if dry_run:
        print("[dry-run] 메일 발송 생략", flush=True)
        return 1
    send(subject, body)
    print(f"{stamp} 알림 발송 완료", flush=True)
    return 1


if __name__ == "__main__":
    # 이상이 있으면 종료코드 1 — 수집 스크립트와 같은 규약이다(호스트 cron 로그에서 실패로 보이게).
    # k8s CronJob은 --exit-zero로 돈다: 이상은 메일로 알리는 정상 동작인데, 종료코드 1이면 잡이 Failed가 되고
    # 재시도(backoffLimit)로 같은 알림이 세 번 나갔다(2026-09-18 09:00 실측 3회).
    code = main()
    sys.exit(0 if "--exit-zero" in sys.argv else code)
