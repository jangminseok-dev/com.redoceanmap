"""뉴스 이벤트 사후 수익률 연구 — news_labels × price_bars.

hub CLAUDE가 "라벨은 학습 피처, 정답은 실현 수익률(price_bars 조인)"이라 선언해 놓고
구현이 없었다. 이 스크립트가 그 조인을 처음 수행한다.

`backtest_area_score.py`와 같은 성격이다 — 요청마다 계산할 것이 아니라 수동 배치로
돌려 결과를 읽는다. 집계 로직은 순수 도메인(`stock/domain/services/event_study.py`)이
소유하고, 여기서는 조회와 출력만 한다.

**결과를 사용자 화면에 그대로 올리면 안 된다.** 절대 수익률은 표본 기간의 시장 방향을
그대로 반영한다 — 기준선 대비(excess)로 읽어야 하고, 표본이 특정 주에 몰려 있으면
관측 수가 커도 독립 관측이 아니다. 리포트가 그 경고를 함께 낸다.

    python scripts/study_news_events.py                # 5일 지평 + 30·60분, 리포트 저장
    python scripts/study_news_events.py --horizon 1
    python scripts/study_news_events.py --minutes 15 30 60
    python scripts/study_news_events.py --dry-run     # 출력만, 저장 생략

**감성 서프라이즈 월례 채점(2026-09-21)** — 분석의 방향 점수에서 뺀 감성을 되살릴지 정하는 검증을 같은 실행에서 함께 낸다
(`stock/domain/services/sentiment_signal_study.py`, 조건도 거기). k8s CronJob `study-news-events`가 매월 1일 07:00에 돌리고,
조건을 넘으면 메일로 알린다 — 넘기 전에는 아무 일도 하지 않는다.

**분 단위 지평(E1)은 5분봉으로 잰다.** 두 가지 한계를 리포트에 명시한다:
1. 5분봉은 소급 수집이 안 된다 — 보유 시작일 이전 발행은 측정 자체가 불가능하다.
2. 장 마감 뒤 발행은 "다음 존재하는 5분봉"이 다음 개장가라, 30분 수익률이 아니라
   밤샘 갭이 된다. 실제 경과 시간이 지평의 GAP_TOLERANCE배를 넘으면 표본에서 뺀다.
"""

import argparse
import sys
from pathlib import Path

from dataclasses import asdict

from sqlalchemy import create_engine, insert, text

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))
from core.key.secret_manager import get_secret_manager  # noqa: E402
from stock.adapter.outbound.orm.news_event_study_report_orm import (  # noqa: E402
    NewsEventStudyReportOrm,
)
from stock.domain.services import sentiment_signal_study  # noqa: E402
from stock.domain.services.event_study import (  # noqa: E402
    EventSample,
    aggregate,
    aggregate_intraday,
)

_secrets = get_secret_manager()
engine = create_engine(
    _secrets.require("DATABASE_URL").replace("postgresql://", "postgresql+psycopg://")
)

# 발행 시각 이후 첫 일봉을 기준(p0), horizon일 뒤 첫 일봉을 결과(p1)로 잡는다.
# 장외 발행은 "다음 개장 첫 봉"이 되며 이는 stock CLAUDE에 명문화된 규칙이다.
_SQL = text("""
SELECT l.event_type, l.sentiment,
       to_char(date_trunc('week', a.published_at), 'YYYY-MM-DD') AS week,
       (SELECT p.close FROM price_bars p
         WHERE p.ticker = a.ticker AND p.timeframe = '1d' AND p.ts >= a.published_at
         ORDER BY p.ts LIMIT 1) AS p0,
       (SELECT p.close FROM price_bars p
         WHERE p.ticker = a.ticker AND p.timeframe = '1d'
           AND p.ts >= a.published_at + make_interval(days => :horizon + 2)
         ORDER BY p.ts LIMIT 1) AS p1
  FROM news_labels l
  JOIN news_articles a ON a.id = l.news_id
 WHERE a.ticker IS NOT NULL AND a.published_at IS NOT NULL AND l.event_type IS NOT NULL
""")


# 실제 경과 시간이 지평의 이 배수를 넘으면 그 표본은 지평을 재고 있지 않다(밤샘 갭·주말).
# 5분봉 간격이 5분이라 30분 지평에서 한두 봉 빈 정도는 통과시키되, 개장 갭은 걸러낸다.
GAP_TOLERANCE = 3.0

# 발행 직후 첫 5분봉을 기준(q0), **그 봉으로부터** minutes분 뒤 첫 5분봉을 결과(q1)로 잡는다.
# `ts >= ...` + LIMIT 1이 곧 "다음 **존재하는** 봉"이라 휴장 캘린더를 하드코딩하지 않는다.
#
# ⚠ q1을 `published_at + minutes`에 걸면 안 된다. 장 마감 뒤 발행이면 q0와 q1이 **같은
#   개장 봉**으로 떨어져 수익률이 0이 된다 — 2026-08-20 실측으로 표본의 75.1%가 그랬고,
#   그 결과 양(+) 비율이 9%까지 내려가는 가짜 리포트가 나왔다. 기준은 진입한 봉이다.
# 봉 시각을 함께 받는 이유는 갭 판정 때문이다 — 값만 받으면 밤샘 갭을 30분 수익률로 오인한다.
_SQL_INTRADAY = text("""
SELECT l.event_type, l.sentiment,
       to_char(date_trunc('week', a.published_at), 'YYYY-MM-DD') AS week,
       q0.close AS p0, q1.close AS p1, q0.ts AS t0, q1.ts AS t1
  FROM news_labels l
  JOIN news_articles a ON a.id = l.news_id
  LEFT JOIN LATERAL (
        SELECT p.close, p.ts FROM price_bars p
         WHERE p.ticker = a.ticker AND p.timeframe = '5m' AND p.ts >= a.published_at
         ORDER BY p.ts LIMIT 1) q0 ON TRUE
  LEFT JOIN LATERAL (
        SELECT p.close, p.ts FROM price_bars p
         WHERE p.ticker = a.ticker AND p.timeframe = '5m'
           AND p.ts >= q0.ts + make_interval(mins => :minutes)
         ORDER BY p.ts LIMIT 1) q1 ON TRUE
 WHERE a.ticker IS NOT NULL AND a.published_at IS NOT NULL AND l.event_type IS NOT NULL
""")

_SQL_5M_COVERAGE = text(
    "SELECT min(ts)::date, max(ts)::date, count(*) FROM price_bars WHERE timeframe = '5m'"
)


def _intraday_report(con, minutes: int):
    """분 단위 지평 1개를 집계한다. 반환: (리포트, 갭으로 버린 건수)."""
    oldest, newest, bar_count = con.execute(_SQL_5M_COVERAGE).one()
    coverage_note = (
        f"5분봉 보유 구간 {oldest} ~ {newest} ({bar_count:,}봉). 5분봉은 소급 수집이 되지 않아 "
        f"{oldest} 이전 발행 뉴스는 측정 대상에서 빠진다 — 표본 수를 일간 리포트와 직접 비교하지 않는다."
    )

    rows = con.execute(_SQL_INTRADAY, {"minutes": minutes}).all()
    samples, gapped = [], 0
    for event_type, sentiment, week, p0, p1, t0, t1 in rows:
        if not (p0 and p1 and float(p0) > 0 and t0 and t1):
            continue
        # 장 마감을 걸치면 t1이 다음 개장가라 이 값은 30분 수익률이 아니라 밤샘 갭이다.
        # t1 == t0(같은 봉)도 여기서 걸린다 — 0초는 지평을 재지 않은 것이다.
        elapsed = (t1 - t0).total_seconds()
        if elapsed <= 0 or elapsed > minutes * 60 * GAP_TOLERANCE:
            gapped += 1
            continue
        samples.append(
            EventSample(
                event_type=event_type,
                sentiment=float(sentiment or 0.0),
                return_pct=(float(p1) - float(p0)) / float(p0) * 100,
                week=week,
            )
        )
    return aggregate_intraday(samples, minutes, coverage_note), gapped, len(rows)


def _print_buckets(report) -> None:
    for title, buckets in (("이벤트 유형", report.by_event), ("감성대", report.by_sentiment)):
        print(f"\n{title}별 (초과수익 = 평균 − 기준선):")
        for b in buckets:
            mark = "" if b.reliable else "  ※표본부족"
            print(
                f"  {b.key:14} n={b.n:>6,}  평균 {b.avg_return_pct:+6.2f}%  "
                f"초과 {b.excess_pct:+6.2f}%p  양(+) {b.positive_rate:.0%}{mark}"
            )


# 감성 서프라이즈 채점 재료 — 기본 라벨러의 종목·발행일별 감성 합과 기사 수, 그리고 일봉 종가.
# 한국 일봉은 KST 자정이 UTC 전날 15:00로 저장된다 — 12시간을 더해 날짜를 읽으면 미국(04:00 UTC)·한국 모두 거래일과 맞는다.
_SQL_SENTIMENT_DAILY = text("""
    select split_part(a.ticker, '.', 1), (a.published_at at time zone 'UTC')::date, sum(l.sentiment), count(*)
    from news_labels l join news_articles a on a.id = l.news_id
    where a.ticker is not null and l.labeler = :labeler and a.published_at >= '2026-01-01'
    group by 1, 2
""")
_SQL_DAILY_CLOSES = text("""
    select split_part(ticker, '.', 1), (ts + interval '12 hours')::date, close
    from price_bars where timeframe = '1d' and ts >= '2026-01-01' order by 1, 2
""")
SURPRISE_HORIZONS = (5, 20)


def _surprise_studies(con) -> list:
    from core.llm.labeler import labeler_tag
    labeler = labeler_tag(_secrets.get("LLM_MODEL", "gemma4:e4b-it-qat"))   # 화면이 읽는 기본 라벨러(news_pg_repository.DEFAULT_LABELER)와 같은 규칙
    daily = [(t, d, float(total), int(n)) for t, d, total, n in con.execute(_SQL_SENTIMENT_DAILY, {"labeler": labeler}).all()]
    closes: dict[str, list] = {}
    for t, d, close in con.execute(_SQL_DAILY_CLOSES).all():
        closes.setdefault(t, []).append((d, float(close)))
    return [sentiment_signal_study.study(daily, closes, h) for h in SURPRISE_HORIZONS]


def _send_ready_mail(studies) -> None:
    """되살림 검토 조건을 넘은 달에만 메일 — check_freshness와 같은 창구(n8n 웹훅). 실패해도 리포트 저장은 끝난 뒤다."""
    import requests
    to = _secrets.get("ALERT_EMAIL")
    if not to:
        print("  ⚠ ALERT_EMAIL 미설정 — 조건 충족 알림을 보내지 못했습니다")
        return
    body = "\n".join(["감성 서프라이즈가 되살림 검토 조건을 넘었습니다.", "", *[f"· {s.horizon_days}거래일: {s.verdict}" for s in studies],
                      "", "조치: stock/_docs/CLAUDE.md '분석도 활성 검증 조합으로 판정' 절을 보고 재적합 후보에 감성을 넣을지 검토하세요."])
    requests.post(_secrets.require("N8N_EMAIL_WEBHOOK_URL"), json={"to": to, "subject": "[RedOcean] 감성 신호 되살림 검토 조건 충족", "body": body},
                  headers={"X-Webhook-Token": _secrets.get("N8N_OUTBOUND_TOKEN", "")}, timeout=30).raise_for_status()


def main(horizon: int, minutes: list[int], dry_run: bool) -> None:
    with engine.connect() as con:
        rows = con.execute(_SQL, {"horizon": horizon}).all()

    samples = [
        EventSample(
            event_type=event_type,
            sentiment=float(sentiment or 0.0),
            return_pct=(float(p1) - float(p0)) / float(p0) * 100,
            week=week,
        )
        for event_type, sentiment, week, p0, p1 in rows
        if p0 and p1 and float(p0) > 0
    ]
    report = aggregate(samples, horizon_days=horizon)

    print(f"조인 후보 {len(rows):,}건 → 수익률 산출 가능 {report.total:,}건 (지평 {horizon}일)")
    print(f"기준선(전체 평균) {report.baseline_pct:+.2f}%  ·  최다 주 비중 {report.top_week_share:.0%}")
    for w in report.warnings:
        print(f"  ⚠ {w}")

    _print_buckets(report)

    # ── 분 단위 지평(E1) — 발행 직후 반응. 같은 실행에서 함께 낸다(같은 표본·같은 규칙).
    shorts = []
    with engine.connect() as con:
        for m in minutes:
            short, gapped, candidates = _intraday_report(con, m)
            shorts.append(short)
            print(f"\n[{m}분 지평] 조인 후보 {candidates:,}건 → 측정 {short.total:,}건 "
                  f"(장외 갭으로 제외 {gapped:,}건)")
            print(f"기준선 {short.baseline_pct:+.3f}%  ·  최다 주 비중 {short.top_week_share:.0%}")
            print(f"  · {short.coverage_note}")
            for w in short.warnings:
                print(f"  ⚠ {w}")
            _print_buckets(short)

    # ── 감성 서프라이즈 월례 채점 — 분석의 방향 점수에 되살릴지(조건은 sentiment_signal_study 상수)
    with engine.connect() as con:
        studies = _surprise_studies(con)
    print("\n[감성 서프라이즈 → 이후 수익률] 같은 날 두 종목을 견줘 값이 높은 쪽이 맞힌 비율")
    for st in studies:
        months = " · ".join(f"{m.month} {m.hit_rate:.1%}({m.observations:,})" for m in st.months if m.hit_rate is not None)
        print(f"  {st.horizon_days:>2}거래일: 관측 {st.observations:,} · 날짜 {st.dates} · 짝 {st.pairs:,} · 적중 "
              f"{'-' if st.hit_rate is None else f'{st.hit_rate:.1%}'}\n      월별: {months}\n      → {st.verdict}")

    if dry_run:
        print("\n--dry-run — INSERT 생략")
        return
    payload = asdict(report)
    payload["short_horizon"] = [asdict(s) for s in shorts]
    payload["sentiment_surprise"] = [asdict(st) for st in studies]
    with engine.begin() as conn:
        conn.execute(insert(NewsEventStudyReportOrm).values(
            params={"horizon_days": horizon, "horizon_minutes": minutes}, payload=payload,
        ))
    print("\nnews_event_study_reports에 리포트 1행 저장 완료")
    if any(st.ready for st in studies):
        try:
            _send_ready_mail(studies)
        except Exception as e:  # 알림 실패가 저장된 리포트를 무효로 만들지 않는다
            print(f"  ⚠ 조건 충족 알림 발송 실패: {e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="뉴스 이벤트 사후 수익률 연구")
    ap.add_argument("--horizon", type=int, default=5, help="일 단위 지평(거래일 근사, 기본 5)")
    ap.add_argument("--minutes", type=int, nargs="*", default=[30, 60],
                    help="분 단위 지평(5분봉 기준, 기본 30 60). 빈 값이면 생략")
    ap.add_argument("--dry-run", action="store_true", help="저장 없이 출력만")
    args = ap.parse_args()
    main(args.horizon, args.minutes, args.dry_run)
