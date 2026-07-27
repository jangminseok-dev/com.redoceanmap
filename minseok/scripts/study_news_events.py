"""뉴스 이벤트 사후 수익률 연구 — news_labels × price_bars.

hub CLAUDE가 "라벨은 학습 피처, 정답은 실현 수익률(price_bars 조인)"이라 선언해 놓고
구현이 없었다. 이 스크립트가 그 조인을 처음 수행한다.

`backtest_area_score.py`와 같은 성격이다 — 요청마다 계산할 것이 아니라 수동 배치로
돌려 결과를 읽는다. 집계 로직은 순수 도메인(`stock/domain/services/event_study.py`)이
소유하고, 여기서는 조회와 출력만 한다.

**결과를 사용자 화면에 그대로 올리면 안 된다.** 절대 수익률은 표본 기간의 시장 방향을
그대로 반영한다 — 기준선 대비(excess)로 읽어야 하고, 표본이 특정 주에 몰려 있으면
관측 수가 커도 독립 관측이 아니다. 리포트가 그 경고를 함께 낸다.

    python scripts/study_news_events.py                # 5일 지평, 리포트 저장
    python scripts/study_news_events.py --horizon 1
    python scripts/study_news_events.py --dry-run     # 출력만, 저장 생략
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
from stock.domain.services.event_study import EventSample, aggregate  # noqa: E402

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


def main(horizon: int, dry_run: bool) -> None:
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

    for title, buckets in (("이벤트 유형", report.by_event), ("감성대", report.by_sentiment)):
        print(f"\n{title}별 (초과수익 = 평균 − 기준선):")
        for b in buckets:
            mark = "" if b.reliable else "  ※표본부족"
            print(
                f"  {b.key:14} n={b.n:>6,}  평균 {b.avg_return_pct:+6.2f}%  "
                f"초과 {b.excess_pct:+6.2f}%p  양(+) {b.positive_rate:.0%}{mark}"
            )

    if dry_run:
        print("\n--dry-run — INSERT 생략")
        return
    with engine.begin() as conn:
        conn.execute(insert(NewsEventStudyReportOrm).values(
            params={"horizon_days": horizon}, payload=asdict(report),
        ))
    print("\nnews_event_study_reports에 리포트 1행 저장 완료")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="뉴스 이벤트 사후 수익률 연구")
    ap.add_argument("--horizon", type=int, default=5, help="지평(거래일 기준 근사, 기본 5)")
    ap.add_argument("--dry-run", action="store_true", help="저장 없이 출력만")
    args = ap.parse_args()
    main(args.horizon, args.dry_run)
