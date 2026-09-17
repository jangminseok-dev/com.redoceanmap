"""상권 점수 워크포워드 백테스트 — 분기 t 점수(v2)로 그 뒤 1년의 실제 폐업률을 채점한다.

과거 분기 t까지의 데이터만으로 area_scorer v2 점수·등급을 재현하고(룩어헤드 방지 — 입력 조립은
런타임과 같은 `inputs_from_aggregates`, 벤치마크는 **그 분기의** 서울 중앙값), t 이후 결과와 대조한다.

- 주 결과: t+1~t+4 점포 가중 폐업률(%) — 창업자가 묻는 "여기 열면 버티나"에 가장 가까운 관측치.
  4분기가 다 있는 t만 쓴다(최신 4분기는 평가 불가).
- 참고 결과: t+1 상대 유동인구 QoQ(상권 − 서울 %p, v1 시절 주 결과) · t+1 매출 QoQ(%).
- 평가 분기: 점포·매출 팩트 2021년 1분기~ → t는 과거 4분기(폐업률 창)와 4분기 뒤가 모두 있는 분기.
- 집계는 순수 도메인 서비스 AreaScoreBacktester가 담당(payload 스키마의 단일 정의처),
  이 스크립트는 I/O(벌크 로드·INSERT)와 관측 조립만 한다(ingest_seoul_3nf 관례).

실행:
    python scripts/backtest_area_score.py            # 백테스트 + 리포트 INSERT
    python scripts/backtest_area_score.py --dry-run  # 요약 출력만 (INSERT 생략)

스케줄: k8s CronJob backtest-area-score(매주 목 06:00, 서울 분기 수집 다음 날).
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
from market.domain.services.area_scorer import (  # noqa: E402
    AreaScorer,
    inputs_from_aggregates,
    median_inputs,
    prev_quarter,
)
from market.domain.value_objects.area_score_vo import MetricComparison  # noqa: E402

# market 전용 DB(:5434) 우선 — 미설정 환경은 메인 DB 폴백(런타임 전환과 동일 규칙).
engine = create_engine(
    (_secrets.get("MARKET_DATABASE_URL") or _secrets.require("DATABASE_URL"))
    .replace("postgresql://", "postgresql+psycopg://")
)

# 서울 상권 집합 — 팩트 → trade_area → 행정동 → 자치구(런타임 _SCORE_INPUTS_SQL의 scope와 같은 경로)
_SEOUL_AREAS = f"""
    SELECT ta.code FROM trade_area ta
    JOIN region dong ON ta.region_code = dong.code
    JOIN region gu ON dong.parent_code = gu.code
    WHERE gu.parent_code = '{SIDO_SEOUL}'
"""


def next_quarter(year_quarter: int) -> int:
    year, quarter = divmod(year_quarter, 10)
    if quarter == 4:
        return (year + 1) * 10 + 1
    return year_quarter + 1


def load() -> dict[str, dict]:
    print("팩트 벌크 로드 중…")
    store = pd.read_sql(text(
        "SELECT trdar_code, year_quarter, SUM(similar_industry_store_count) AS sc, SUM(closure_store_count) AS cc"
        f" FROM store WHERE trdar_code IN ({_SEOUL_AREAS}) GROUP BY 1, 2"
    ), engine)
    sales = pd.read_sql(text(
        "SELECT es.trdar_code, es.year_quarter, SUM(es.monthly_sales_amount) AS amt, SUM(s.similar_industry_store_count) AS sal_sc"
        " FROM estimated_sales es JOIN store s ON s.trdar_code = es.trdar_code"
        " AND s.year_quarter = es.year_quarter AND s.service_code = es.service_code"
        f" WHERE s.similar_industry_store_count > 0 AND es.trdar_code IN ({_SEOUL_AREAS}) GROUP BY 1, 2"
    ), engine)
    months = pd.read_sql(text(
        f"SELECT trdar_code, year_quarter, operating_months_avg AS om FROM commercial_change"
        f" WHERE trdar_code IN ({_SEOUL_AREAS})"
    ), engine)
    floating = pd.read_sql(text(
        f"SELECT trdar_code, year_quarter, total_floating_pop AS fp FROM floating_population"
        f" WHERE trdar_code IN ({_SEOUL_AREAS})"
    ), engine)
    key = lambda r: (int(r.trdar_code), int(r.year_quarter))  # noqa: E731
    return {
        "store": {key(r): (int(r.sc), int(r.cc)) for r in store.itertuples(index=False)},
        "sales": {key(r): (float(r.amt), int(r.sal_sc)) for r in sales.itertuples(index=False)},
        "months": {key(r): float(r.om) for r in months.itertuples(index=False)},
        "floating": {key(r): float(r.fp) for r in floating.itertuples(index=False)},
        "city_floating": floating.groupby("year_quarter")["fp"].sum().to_dict(),
        "codes": sorted({int(c) for c in store.trdar_code}),
        "quarters": sorted({int(q) for q in store.year_quarter}),
    }


def pct_change(cur: float | None, prev: float | None) -> float | None:
    if cur is None or prev is None or prev <= 0:
        return None
    return (cur / prev - 1) * 100


def build_observations() -> list[ScoredObservation]:
    f = load()
    store, sales = f["store"], f["sales"]
    quarters = set(f["quarters"])
    eval_quarters = [
        t for t in f["quarters"]
        if all(q in quarters for q in _past4(t)) and all(q in quarters for q in _ahead(t, 4))
    ]
    print(f"평가 분기 {len(eval_quarters)}개: {eval_quarters[0]}~{eval_quarters[-1]}")

    scorer = AreaScorer()
    observations: list[ScoredObservation] = []
    for t in eval_quarters:
        past4 = _past4(t)
        inputs = {}
        for code in f["codes"]:
            if (code, t) not in store:
                continue
            window = [store[(code, q)] for q in past4 if (code, q) in store]
            sc_sum = sum(sc for sc, _ in window)
            amt, sal_sc = sales.get((code, t), (None, None))
            inputs[code] = inputs_from_aggregates(
                year_quarter=t,
                closure_rate_4q=sum(cc for _, cc in window) * 100 / sc_sum if sc_sum else None,
                quarters_with_stores=len(window),
                store_count=store[(code, t)][0],
                quarterly_sales=amt, sales_store_count=sal_sc,
                operating_months=f["months"].get((code, t)),
            )
        medians = median_inputs(t, list(inputs.values()))
        if medians is None:
            continue

        t1 = next_quarter(t)
        city_flo = pct_change(f["city_floating"].get(t1), f["city_floating"].get(t))
        for code, x in inputs.items():
            score = scorer.score(
                closure_stability=_pair(x.closure_rate_4q, medians.closure_rate_4q),
                persistence=_pair(x.operating_months, medians.operating_months),
                sales_level=_pair(x.sales_per_store_wan, medians.sales_per_store_wan),
            )
            if score is None:
                continue
            future = [store[(code, q)] for q in _ahead(t, 4) if (code, q) in store]
            future_sc = sum(sc for sc, _ in future)
            closure_next4 = (
                sum(cc for _, cc in future) * 100 / future_sc if len(future) == 4 and future_sc else None
            )
            flo = pct_change(f["floating"].get((code, t1)), f["floating"].get((code, t)))
            observations.append(ScoredObservation(
                trdar_code=str(code), year_quarter=t, grade=score.grade, total=score.total,
                component_scores={c.key: c.score for c in score.components},
                outcome_closure_next4=closure_next4,
                outcome_rel_floating_qoq=flo - city_flo if flo is not None and city_flo is not None else None,
                outcome_sales_qoq=pct_change(sales.get((code, t1), (None,))[0], sales.get((code, t), (None,))[0]),
            ))
    return observations


def _past4(t: int) -> list[int]:
    out = [t]
    for _ in range(3):
        out.append(prev_quarter(out[-1]))
    return out


def _ahead(t: int, n: int) -> list[int]:
    out, q = [], t
    for _ in range(n):
        q = next_quarter(q)
        out.append(q)
    return out


def _pair(value: float | None, benchmark: float | None) -> MetricComparison | None:
    if value is None or benchmark is None:
        return None
    return MetricComparison(value=round(value, 2), benchmark=round(benchmark, 2))


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    observations = build_observations()
    payload = AreaScoreBacktester().aggregate(observations)
    params = {
        "base_quarters": f"{payload['base_quarters'][0]}~{payload['base_quarters'][-1]}"
        if payload["base_quarters"] else None,
        "score_version": "v2",
        "outcome": "closure_next4(t+1~t+4 점포 가중 폐업률, %)",
        "sido": SIDO_SEOUL,
    }

    print(f"\n관측 {payload['n_observations']}건 · 상권 {payload['n_areas']}곳")
    print("등급별 향후 4분기 폐업률(주 결과) · t+1 상대 유동인구 QoQ(참고):")
    for row in payload["grade_outcomes"]:
        closure = row["avg_closure_next4"]
        floating = row["avg_rel_floating_qoq"]
        detail = f" 폐업률={closure:.2f}% (n={row['closure_n']})" if closure is not None else ""
        detail += f" 유동 avg={floating:+.2f}%p" if floating is not None else ""
        print(f"  {row['grade']}: n={row['n']}{detail}")
    print("컴포넌트 예측력(Spearman — 양수면 점수가 높을수록 덜 닫음 · 5분위 스프레드 = 하위−상위 폐업률):")
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
