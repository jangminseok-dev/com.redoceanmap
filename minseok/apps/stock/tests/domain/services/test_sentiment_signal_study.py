"""감성 서프라이즈 월례 채점 — 창·최소 표본·짝 비교·되살림 조건(2026-09-21에 정한 기준을 결과 보고 옮기지 않게 고정)."""
from datetime import date, timedelta

from stock.domain.services import sentiment_signal_study as S


def test_서프라이즈는_최근_7일_평균에서_30일_평균을_뺀_값이고_표본이_모자란_날은_뺀다():
    start = date(2026, 7, 1)
    # 30일 동안 매일 기사 1건 감성 0.0, 마지막 3일만 +0.9
    daily = [("A", start + timedelta(days=i), 0.9 if i >= 27 else 0.0, 1) for i in range(30)]
    series = S.surprise_series(daily)["A"]
    last = start + timedelta(days=29)
    assert round(series[last], 4) == round((0.9 * 3 / 7) - (0.9 * 3 / 30), 4)
    assert start not in series and start + timedelta(days=3) not in series   # 기준선 5건·최근 3건을 못 채운 초반
    assert min(series) == start + timedelta(days=4)


def _market(months: int, predictive: bool, tickers: int = 12):
    """달마다 거래일 20일 · 종목마다 고정된 서프라이즈 순위. predictive면 순위대로 오르고, 아니면 달마다 방향이 뒤집힌다."""
    start = date(2026, 1, 1)
    days = [start + timedelta(days=i) for i in range(months * 31 + 40)]
    daily, closes = [], {}
    for k in range(tickers):
        t = f"T{k}"
        # 감성이 종목마다 다른 기울기로 꾸준히 오른다 → 최근 7일 평균 − 30일 평균(서프라이즈)이 늘 k에 비례해 순위가 유지된다
        daily += [(t, d, k * i * 1e-4 * 3, 3) for i, d in enumerate(days)]
        price, series = 100.0, []
        for i, d in enumerate(days):
            sign = 1 if predictive or (d.month % 2 == 0) else -1
            price *= 1 + sign * (k - tickers / 2) * 0.0005
            series.append((d, price))
        closes[t] = series
    return daily, closes


def test_예측력이_있고_달이_충분히_쌓이면_되살림_검토_조건을_넘는다():
    daily, closes = _market(months=7, predictive=True)
    study = S.study(daily, closes, horizon_days=5)
    assert study.hit_rate > 0.9 and study.ready and study.verdict.startswith("되살림 검토 조건 충족")
    assert len([m for m in study.months if m.observations >= S.GATE_MIN_MONTH_OBS]) >= S.GATE_MIN_MONTHS


def test_적중률이_높아도_달이_모자라면_되살리지_않는다():
    daily, closes = _market(months=3, predictive=True)
    study = S.study(daily, closes, horizon_days=5)
    assert study.hit_rate > 0.9 and not study.ready
    assert study.verdict.startswith("가중치 0 유지")


def test_달마다_방향이_뒤집히면_기간이_길어도_되살리지_않는다():
    daily, closes = _market(months=8, predictive=False)
    study = S.study(daily, closes, horizon_days=5)
    assert not study.ready and 0.35 < study.hit_rate < 0.65   # 동전 던지기 근처 — 실측(2026-06~09)과 같은 모양


def test_기준은_2026_09_21에_정한_값이다():
    """결과를 보고 기준을 옮기면 검증이 아니다 — 바꿀 때는 이 테스트와 함께 근거를 남긴다."""
    assert (S.GATE_MIN_MONTHS, S.GATE_MIN_MONTH_OBS, S.GATE_MIN_HIT_RATE, S.GATE_MIN_CONSISTENT) == (6, 200, 0.53, 5)
    assert (S.RECENT_DAYS, S.BASELINE_DAYS, S.MIN_RECENT, S.MIN_BASELINE) == (7, 30, 3, 5)
