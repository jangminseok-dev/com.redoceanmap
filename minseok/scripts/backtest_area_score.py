"""상권 점수 워크포워드 백테스트 — 분기 t 점수로 t+1 실제 결과를 채점한다.

과거 분기 t 데이터만으로 area_scorer 점수·등급을 재현하고(룩어헤드 방지 — 분기 t의
정확한 QoQ만 사용, 런타임의 "최신 유효 QoQ" 폴백 없음), t+1 분기의 실제 결과와 대조한다.

- 주 결과 지표: t+1 상대 유동인구 QoQ(상권 − 서울, %p) — 시 전체 대비 차분으로 계절성 통제.
- 컴포넌트 가용성: 유동인구 성장·영업 지속성은 28분기(20191~), 매출 성장·개폐업 건강도는
  2025년 4분기뿐(t→t+1 쌍 3개) — 매출 결과(outcome_sales_qoq)는 저표본 참고치로만 부기.
- 집계는 순수 도메인 서비스 AreaScoreBacktester가 담당(payload 스키마의 단일 정의처),
  이 스크립트는 I/O(벌크 로드·INSERT)와 관측 조립만 한다(ingest_seoul_3nf 관례).

실행:
    python scripts/backtest_area_score.py            # 백테스트 + 리포트 INSERT
    python scripts/backtest_area_score.py --dry-run  # 요약 출력만 (INSERT 생략)

수동 실행 전용(분기 데이터 갱신 후) — cron 불요.
"""

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, insert, text

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))
from core.key.secret_manager import get_secret_manager  # noqa: E402

_secrets = get_secret_manager()

SIDO_SEOUL = "11"

from market.adapter.outbound.orm.area_backtest_report_orm import AreaBacktestReportOrm  # noqa: E402
from market.domain.services.area_score_backtester import (  # noqa: E402
    AreaScoreBacktester,
    ScoredObservation,
)
from market.domain.services.area_scorer import AreaScorer, prev_quarter  # noqa: E402
from market.domain.value_objects.area_score_vo import MetricComparison  # noqa: E402

# market 전용 DB(:5434) 우선 — 미설정 환경은 메인 DB 폴백(런타임 전환과 동일 규칙).
# 괄호 주의: .replace가 폴백 분기에만 묶이면 MARKET_DATABASE_URL을 쓸 때 드라이버
# 접두사가 안 붙어 psycopg2를 찾다 죽는다(ingest 스크립트와 동일 수정).
engine = create_engine(
    (_secrets.get("MARKET_DATABASE_URL") or _secrets.require("DATABASE_URL"))
    .replace("postgresql://", "postgresql+psycopg://")
)

# 팩트 → trade_area → 행정동 → 자치구 조인으로 서울 상권만 집계 (_sido_join과 동일 경로)
_SIDO_JOIN = """
    JOIN trade_area ta ON f.trdar_code = ta.code
    JOIN region dong ON ta.region_code = dong.code
    JOIN region gu ON dong.parent_code = gu.code
"""


def next_quarter(year_quarter: int) -> int:
    year, quarter = divmod(year_quarter, 10)
    if quarter == 4:
        return (year + 1) * 10 + 1
    return year_quarter + 1


def load_area_series(sql: str) -> dict[int, dict[int, float]]:
    """trdar_code → {year_quarter → value}."""
    df = pd.read_sql(text(sql), engine)
    out: dict[int, dict[int, float]] = {}
    for code, yq, value in df.itertuples(index=False):
        out.setdefault(int(code), {})[int(yq)] = float(value)
    return out


def load_city_series(sql: str) -> dict[int, float]:
    df = pd.read_sql(text(sql), engine)
    return {int(yq): float(value) for yq, value in df.itertuples(index=False)}


def qoq(series: dict[int, float], quarter: int) -> float | None:
    """분기 quarter의 정확한 QoQ(%) — 직전 분기 결측·0 이하면 None (폴백 없음)."""
    prev = series.get(prev_quarter(quarter))
    cur = series.get(quarter)
    if prev is None or cur is None or prev <= 0:
        return None
    return (cur - prev) / prev * 100


def build_observations() -> list[ScoredObservation]:
    print("팩트 벌크 로드 중…")
    area_floating = load_area_series(
        "SELECT trdar_code, year_quarter, total_floating_pop FROM floating_population"
    )
    city_floating = load_city_series(
        "SELECT f.year_quarter, SUM(f.total_floating_pop) FROM floating_population f"
        + _SIDO_JOIN + f" WHERE gu.parent_code = '{SIDO_SEOUL}' GROUP BY f.year_quarter"
    )
    area_sales = load_area_series(
        "SELECT trdar_code, year_quarter, SUM(monthly_sales_amount)"
        " FROM estimated_sales GROUP BY trdar_code, year_quarter"
    )
    city_sales = load_city_series(
        "SELECT f.year_quarter, SUM(f.monthly_sales_amount) FROM estimated_sales f"
        + _SIDO_JOIN + f" WHERE gu.parent_code = '{SIDO_SEOUL}' GROUP BY f.year_quarter"
    )
    area_store = pd.read_sql(text(
        "SELECT trdar_code, year_quarter,"
        " AVG(opening_rate) AS opening, AVG(closure_rate) AS closure"
        " FROM store GROUP BY trdar_code, year_quarter"
    ), engine)
    store_health = {
        (int(r.trdar_code), int(r.year_quarter)): (float(r.opening), float(r.closure))
        for r in area_store.itertuples(index=False)
    }
    city_store = pd.read_sql(text(
        "SELECT f.year_quarter, AVG(f.opening_rate) AS opening, AVG(f.closure_rate) AS closure"
        " FROM store f" + _SIDO_JOIN
        + f" WHERE gu.parent_code = '{SIDO_SEOUL}' GROUP BY f.year_quarter"
    ), engine)
    city_store_health = {
        int(r.year_quarter): (float(r.opening), float(r.closure))
        for r in city_store.itertuples(index=False)
    }
    area_persistence = load_area_series(
        "SELECT trdar_code, year_quarter, operating_months_avg FROM commercial_change"
    )
    bench_persistence = load_city_series(
        "SELECT year_quarter, operating_months_avg FROM commercial_change_benchmark"
        f" WHERE region_code = '{SIDO_SEOUL}'"
    )

    # 평가 분기 t: 서울 유동인구 QoQ가 t와 t+1 모두 계산 가능한 분기(t-1·t·t+1 존재)
    eval_quarters = sorted(
        q for q in city_floating
        if qoq(city_floating, q) is not None
        and qoq(city_floating, next_quarter(q)) is not None
    )
    print(f"평가 분기 {len(eval_quarters)}개: {eval_quarters[0]}~{eval_quarters[-1]}")

    scorer = AreaScorer()
    observations: list[ScoredObservation] = []
    for t in eval_quarters:
        t1 = next_quarter(t)
        city_flo_t = qoq(city_floating, t)
        city_flo_t1 = qoq(city_floating, t1)
        city_sal_t = qoq(city_sales, t)
        bench_pers_t = bench_persistence.get(t)
        city_sh_t = city_store_health.get(t)

        for code, series in area_floating.items():
            # 분기 t 시점 점수 재현 — 각 컴포넌트는 정확히 t의 값만 사용
            flo_t = qoq(series, t)
            floating_growth = (
                MetricComparison(value=flo_t, benchmark=city_flo_t)
                if flo_t is not None and city_flo_t is not None else None
            )
            pers_t = area_persistence.get(code, {}).get(t)
            persistence = (
                MetricComparison(value=pers_t, benchmark=bench_pers_t)
                if pers_t is not None and bench_pers_t is not None and bench_pers_t > 0
                else None
            )
            sal_t = qoq(area_sales.get(code, {}), t)
            sales_growth = (
                MetricComparison(value=sal_t, benchmark=city_sal_t)
                if sal_t is not None and city_sal_t is not None else None
            )
            sh = store_health.get((code, t))
            store_comp = (
                MetricComparison(value=sh[0] - sh[1], benchmark=city_sh_t[0] - city_sh_t[1])
                if sh is not None and city_sh_t is not None else None
            )

            score = scorer.score(
                sales_growth=sales_growth, floating_growth=floating_growth,
                store_health=store_comp, persistence=persistence,
            )
            if score is None:
                continue

            # t+1 결과 — 상대 유동인구 QoQ(%p). 없으면 관측 제외
            flo_t1 = qoq(series, t1)
            if flo_t1 is None or city_flo_t1 is None:
                continue
            sal_t1 = qoq(area_sales.get(code, {}), t1)

            observations.append(ScoredObservation(
                trdar_code=str(code), year_quarter=t,
                grade=score.grade, total=score.total,
                component_scores={c.key: c.score for c in score.components},
                outcome_rel_floating_qoq=flo_t1 - city_flo_t1,
                outcome_sales_qoq=sal_t1,
            ))
    return observations


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    observations = build_observations()
    payload = AreaScoreBacktester().aggregate(observations)
    params = {
        "base_quarters": f"{payload['base_quarters'][0]}~{payload['base_quarters'][-1]}"
        if payload["base_quarters"] else None,
        "outcome": "rel_floating_qoq(t+1, 상권−서울 %p)",
        "sido": SIDO_SEOUL,
    }

    print(f"\n관측 {payload['n_observations']}건 · 상권 {payload['n_areas']}곳")
    print("등급별 t+1 상대 유동인구 QoQ:")
    for row in payload["grade_outcomes"]:
        avg = row["avg_rel_floating_qoq"]
        share = row["positive_share"]
        detail = (
            f" avg={avg:+.2f}%p 양(+)비율={share:.1%} sales_n={row['sales_n']}"
            if avg is not None else ""
        )
        print(f"  {row['grade']}: n={row['n']}{detail}")
    print("컴포넌트 예측력(Spearman · 5분위 스프레드):")
    for row in payload["component_predictiveness"]:
        sp = f" ρ={row['spearman']:+.3f}" if row["spearman"] is not None else ""
        spread = (
            f" spread={row['top_minus_bottom_quintile']:+.2f}%p"
            if row["top_minus_bottom_quintile"] is not None else ""
        )
        print(f"  {row['key']}: n={row['n']}{sp}{spread}")

    if dry_run:
        print("\n--dry-run — INSERT 생략")
        return
    with engine.begin() as conn:
        conn.execute(insert(AreaBacktestReportOrm).values(params=params, payload=payload))
    print("\narea_score_backtest_reports에 리포트 1행 저장 완료")


if __name__ == "__main__":
    main()
