"""펀더멘털 가치 축 워크포워드 백테스트 (E2) — PER/PBR 횡단 분위 → t+60/120거래일 수익률.

질문: "그 시점에 알려진 연간 EPS/BPS로 만든 PER/PBR 분위(횡단 랭킹)가 이후 60~120
거래일 수익률을 예측하는가?" 통과해야 단기 방향(기술 신호)과 **분리된 장기 가치 축**으로
노출한다 — 지평이 다른 신호를 섞으면 서로 오염된다(ROADMAP E2).

point-in-time 규칙: 평가일 t에는 as_of ≤ t 인 최신 yf-hist 행(회계연도 말 + 90일 공시
시차 반영, backfill_fundamentals.py)만 쓴다. PER(t)=price(t)/EPS, PBR(t)=price(t)/BPS —
가격은 t 이전 최근 종가. EPS·BPS ≤ 0 은 해당 팩터에서 제외(적자·자본잠식은 비율이 무의미).

방법:
  - 평가일: SPY 거래일 격자에서 EVAL_STEP(21거래일≈월간)마다. 유니버스 MIN_UNIVERSE 미만이면 건너뜀.
  - 분위: 평가일마다 팩터 오름차순 5분위(Q1=저평가) — 종목 횡단 랭킹(시계열 자기 분위 아님).
  - 결과: 각 종목 자체 거래일 기준 t+h 종가 수익률. 초과수익 = 수익률 − 그날 유니버스 평균
    (시장 방향 통제 — 이벤트 연구의 excess 기준과 동일 취지).
  - 판정: Q1의 양(+) 초과수익 비율에 Wilson 95% 하한 > 0.5, 그리고 Q1−Q5 스프레드 > 0,
    그리고 **중첩 보정 유효표본**(n / (h/EVAL_STEP)) ≥ 100. 월간 평가 × 60/120일 지평은
    창이 겹쳐 관측이 독립이 아니다 — 원표본 n으로 게이트를 걸면 소표본 낙관이 된다.

한계(리포트에 병기):
  - 워치리스트는 "오늘의" 목록 — 생존 편향(상폐·급락 퇴출 종목 부재)이 있다.
  - 연간 보고서 4개년(yfinance 상한)이라 평가 창이 ~3년. 거시 국면 1~2개에 걸친 표본이다.

실행(실 DB 읽기 전용 — INSERT 없음, 리포트는 stdout + _docs 마크다운):
    python scripts/backtest_fundamentals.py
    python scripts/backtest_fundamentals.py --no-doc   # 문서 생성 생략

수동 실행 전용(연구) — cron 불요.
"""

import sys
from bisect import bisect_right
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))
from core.key.secret_manager import get_secret_manager  # noqa: E402
from stock.domain.value_objects.backtest_report import wilson_lower_bound  # noqa: E402

_secrets = get_secret_manager()
engine = create_engine(
    _secrets.require("DATABASE_URL").replace("postgresql://", "postgresql+psycopg://")
)

FACTORS = ("per", "pbr")
HORIZONS = (60, 120)          # 거래일 — 분기~반기 가치 지평
EVAL_STEP = 21                # 평가 간격(거래일) ≈ 월간
QUINTILES = 5
MIN_UNIVERSE = 20             # 평가일 최소 종목 수 — 미만이면 분위가 잡음
MIN_EFFECTIVE_N = 100         # 게이트: 중첩 보정 유효표본(재채점 2·3차 n≥100과 같은 기준)
START = date(2022, 10, 1)     # 첫 yf-hist as_of(2022-09-28) 직후
DOC_PATH = ROOT / "apps" / "stock" / "_docs" / "FUNDAMENTAL_BACKTEST_2026-08.md"


def load_data():
    with engine.connect() as conn:
        fund = conn.execute(text(
            "SELECT ticker, as_of, eps, bps FROM fundamental_snapshots "
            "WHERE source = 'yf-hist' ORDER BY ticker, as_of"
        )).all()
        tickers = sorted({r.ticker for r in fund})
        bars = conn.execute(text(
            "SELECT ticker, ts::date AS d, close FROM price_bars "
            "WHERE timeframe = '1d' AND ticker = ANY(:tickers) AND ts >= :start "
            "ORDER BY ticker, ts"
        ), {"tickers": tickers, "start": date(2022, 1, 1)}).all()
        spy_days = [r[0] for r in conn.execute(text(
            "SELECT ts::date FROM price_bars "
            "WHERE timeframe = '1d' AND ticker = 'SPY' AND ts >= :start ORDER BY ts"
        ), {"start": START}).all()]

    fundamentals: dict[str, list] = defaultdict(list)  # ticker → [(as_of, eps, bps)]
    for r in fund:
        fundamentals[r.ticker].append((r.as_of, r.eps, r.bps))
    prices: dict[str, tuple[list, list]] = {}          # ticker → (dates[], closes[])
    by_ticker: dict[str, list] = defaultdict(list)
    for r in bars:
        by_ticker[r.ticker].append((r.d, r.close))
    for tk, rows in by_ticker.items():
        prices[tk] = ([d for d, _ in rows], [c for _, c in rows])
    return fundamentals, prices, spy_days


def latest_at(records: list, t: date):
    """as_of ≤ t 인 최신 행 — point-in-time의 심장. 없으면 None."""
    i = bisect_right([r[0] for r in records], t)
    return records[i - 1] if i else None


def observe(fundamentals, prices, t: date):
    """평가일 t의 (ticker, per, pbr, {h: 수익률}) 관측 목록."""
    out = []
    for tk, records in fundamentals.items():
        rec = latest_at(records, t)
        if rec is None or tk not in prices:
            continue
        _, eps, bps = rec
        dates, closes = prices[tk]
        i = bisect_right(dates, t) - 1
        if i < 0 or (t - dates[i]).days > 7:
            continue  # 시세 공백(상장 전·수집 공백) — 관측 제외
        price = closes[i]
        rets = {
            h: closes[i + h] / price - 1.0
            for h in HORIZONS if i + h < len(dates)
        }
        if not rets:
            continue
        out.append({
            "ticker": tk,
            "per": price / eps if eps and eps > 0 else None,
            "pbr": price / bps if bps and bps > 0 else None,
            "rets": rets,
        })
    return out


def run():
    fundamentals, prices, spy_days = load_data()
    eval_dates = spy_days[::EVAL_STEP]

    # (factor, horizon, quintile) → [초과수익], IC용 (factor, horizon) → [일별 스피어만]
    excess: dict[tuple, list] = defaultdict(list)
    ics: dict[tuple, list] = defaultdict(list)
    used_dates: dict[int, int] = defaultdict(int)

    for t in eval_dates:
        obs = observe(fundamentals, prices, t)
        for h in HORIZONS:
            rows = [o for o in obs if h in o["rets"]]
            if len(rows) < MIN_UNIVERSE:
                continue
            mean_ret = sum(o["rets"][h] for o in rows) / len(rows)
            used_dates[h] += 1
            for factor in FACTORS:
                ranked = sorted(
                    (o for o in rows if o[factor] is not None), key=lambda o: o[factor]
                )
                if len(ranked) < MIN_UNIVERSE:
                    continue
                for idx, o in enumerate(ranked):
                    q = min(QUINTILES, idx * QUINTILES // len(ranked) + 1)
                    excess[(factor, h, q)].append(o["rets"][h] - mean_ret)
                ics[(factor, h)].append(_spearman(
                    [o[factor] for o in ranked], [o["rets"][h] for o in ranked]
                ))

    return _report(excess, ics, used_dates)


def _spearman(xs, ys):
    def rank(vs):
        order = sorted(range(len(vs)), key=lambda i: vs[i])
        r = [0.0] * len(vs)
        for pos, i in enumerate(order):
            r[i] = pos
        return r
    rx, ry = rank(xs), rank(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx) ** 0.5
    vy = sum((b - my) ** 2 for b in ry) ** 0.5
    return cov / (vx * vy) if vx and vy else 0.0


def _report(excess, ics, used_dates):
    lines = []
    verdicts = {}
    for factor in FACTORS:
        for h in HORIZONS:
            qs = {q: excess.get((factor, h, q), []) for q in range(1, QUINTILES + 1)}
            if not qs[1]:
                continue
            n1 = len(qs[1])
            pos1 = sum(1 for v in qs[1] if v > 0)
            avg = {q: (sum(v) / len(v) if v else 0.0) for q, v in qs.items()}
            spread = avg[1] - avg[QUINTILES]
            n_eff = int(n1 / max(1, h // EVAL_STEP))  # 중첩 보정 유효표본
            wilson = wilson_lower_bound(pos1, n1)
            ic = ics.get((factor, h), [])
            mean_ic = sum(ic) / len(ic) if ic else 0.0
            gate = wilson > 0.5 and spread > 0 and n_eff >= MIN_EFFECTIVE_N
            verdicts[(factor, h)] = gate
            lines.append({
                "factor": factor, "horizon": h, "dates": used_dates[h],
                "n_q1": n1, "n_eff": n_eff, "pos_rate": pos1 / n1, "wilson": wilson,
                "avg_q": avg, "spread": spread, "ic": mean_ic, "gate": gate,
            })
    return lines, verdicts


def render(lines, verdicts) -> str:
    now = datetime.now()
    doc = [
        "# 펀더멘털 가치 축 백테스트 — PER/PBR 분위 워크포워드 (E2)",
        "",
        f"실행 {now:%Y-%m-%d %H:%M} · `scripts/backtest_fundamentals.py` (재실행 재현 가능)",
        "",
        "그 시점에 알려진 연간 EPS/BPS(yf-hist, 공시 시차 +90일)로 만든 PER/PBR 횡단",
        f"5분위가 t+60/120거래일 수익률을 예측하는지 — 평가 {EVAL_STEP}거래일 간격,",
        "초과수익 = 종목 수익률 − 그날 유니버스 평균(시장 방향 통제).",
        "",
        "| 팩터 | 지평 | 평가일 | Q1 n(유효) | Q1 양(+)율 | Wilson 하한 | Q1 평균초과 | Q1−Q5 | 평균 IC | 게이트 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in lines:
        doc.append(
            f"| {r['factor'].upper()} | {r['horizon']}일 | {r['dates']} "
            f"| {r['n_q1']}({r['n_eff']}) | {r['pos_rate']:.1%} | {r['wilson']:.3f} "
            f"| {r['avg_q'][1]*100:+.2f}%p | {r['spread']*100:+.2f}%p "
            f"| {r['ic']:+.3f} | {'✅ 통과' if r['gate'] else '⛔ 미달'} |"
        )
    doc += [
        "",
        "분위 평균 초과수익(%p, Q1=저평가 → Q5=고평가):",
        "",
        "| 팩터·지평 | Q1 | Q2 | Q3 | Q4 | Q5 |",
        "|---|---|---|---|---|---|",
    ]
    for r in lines:
        doc.append(
            f"| {r['factor'].upper()} {r['horizon']}일 | "
            + " | ".join(f"{r['avg_q'][q]*100:+.2f}" for q in range(1, QUINTILES + 1))
            + " |"
        )
    doc += [
        "",
        "## 판정 기준",
        "",
        f"Q1 양(+) 초과수익 비율의 Wilson 95% 하한 > 0.5 **그리고** Q1−Q5 스프레드 > 0",
        f"**그리고** 중첩 보정 유효표본(n ÷ (지평/{EVAL_STEP})) ≥ {MIN_EFFECTIVE_N}.",
        "월간 평가 × 60/120일 지평은 창이 겹쳐 관측이 독립이 아니다 — 원표본으로 게이트를",
        "걸면 소표본 낙관이 된다(괄호 안이 유효표본).",
        "",
        "## 한계",
        "",
        "- **생존 편향**: 유니버스가 \"오늘의\" 워치리스트다 — 상폐·급락 퇴출 종목이 없다.",
        "- **짧은 창**: 연간 보고서 4개년(yfinance 상한) → 평가 창 ~3년, 거시 국면 1~2개.",
        "- **혼합 통화**: 한국 2종목이 섞이나 비율(PER/PBR)·수익률은 무단위라 왜곡 없음.",
        "",
        "## 결론",
        "",
    ]
    passed = [f"{f.upper()} {h}일" for (f, h), ok in verdicts.items() if ok]
    if passed:
        doc.append(f"게이트 통과: **{', '.join(passed)}** — 단기 방향과 분리된 장기 가치 축으로")
        doc.append("노출 후보. 노출 형태·문구는 별도 단계에서 결정한다(확률 단정 금지 정책 유지).")
    else:
        doc.append("**전 조합 게이트 미달** — 판정 편입 보류. 현행(펀더멘털은 서술 축으로만)을")
        doc.append("유지하고, 표본이 쌓인 뒤(연간 보고서 추가 축적) 재채점한다.")
    return "\n".join(doc) + "\n"


def main() -> int:
    lines, verdicts = run()
    if not lines:
        print("관측이 없습니다 — yf-hist 백필(backfill_fundamentals.py) 선행 여부를 확인하세요.")
        return 1
    doc = render(lines, verdicts)
    print(doc)
    if "--no-doc" not in sys.argv:
        DOC_PATH.write_text(doc, encoding="utf-8")
        print(f"[리포트 저장] {DOC_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
