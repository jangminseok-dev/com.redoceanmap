"""weight_refit — 재채점 산식·승격 게이트·히스테리시스·멱등·표본 외 구간·실효 표본 검증."""
from datetime import UTC, datetime, timedelta

from stock.domain.entities.analysis_config import AnalysisConfig
from stock.domain.services import weight_refit
from stock.domain.services.weight_refit import (
    DOWN_THRESHOLD,
    PROMOTION_MARGIN,
    RefitSample,
)

CURRENT = AnalysisConfig.forecast_signal()  # RSI+BB+MOM 0.4/0.4/0.2 ±0.35


# atr 1% · 지평 5일 → 변동성 1단위 0.0224, 적중 문턱 0.0056. 아래 표본의 ±0.01~0.03은
# 이 문턱 밖이라 적중 판정이 부호 기준일 때와 같다(옛 기대값 그대로 유효).
def _sample(
    rsi=0.0, bollinger=0.0, momentum=0.0, trend=0.0, obv=0.0, ret=0.01,
    ticker="AAA", atr_pct=0.01, as_of=None,
) -> RefitSample:
    return RefitSample(
        signals={
            "sentiment": 0.0, "rsi": rsi, "trend": trend,
            "bollinger": bollinger, "obv": obv, "momentum": momentum,
        },
        realized_return_pct=ret,
        ticker=ticker,
        atr_pct=atr_pct,
        as_of=as_of,
    )


LATEST = datetime(2026, 9, 1, tzinfo=UTC)


def _dated_universe(n_tickers: int, hit_tickers: int, *, first_day: int, signal=(0.4, 0.4)) -> list[RefitSample]:
    """종목마다 강신호 1건(주 1개) + 무신호 하락 4건 — 실효 표본이 종목 수만큼 나오는 날짜 있는 표본.

    first_day: LATEST로부터 며칠 전에 강신호를 둘지(>14면 선택 구간, ≤14면 표본 외 구간).
    """
    rows = []
    for i in range(n_tickers):
        t = f"T{first_day}_{i}"
        rows.append(_sample(rsi=signal[0], bollinger=signal[1], ret=0.02 if i < hit_tickers else -0.02,
                            ticker=t, as_of=LATEST - timedelta(days=first_day)))
        rows += [_sample(ret=-0.02, ticker=t, as_of=LATEST - timedelta(days=first_day + 7 * (k + 1))) for k in range(4)]
    return rows


def _up_samples(n: int, hit_ratio: float) -> list[RefitSample]:
    """전 후보에서 UP이 발화하는 강신호 표본 — hit_ratio만큼 상승."""
    hits = round(n * hit_ratio)
    return [
        _sample(rsi=1.0, bollinger=1.0, momentum=1.0, trend=1.0, obv=1.0,
                ret=0.02 if i < hits else -0.02)
        for i in range(n)
    ]


def test_점수_산식은_OutlookPredictor와_같다():
    # rsi 0.5×0.4 + bb 0.5×0.4 + mom 0.5×0.2 = 0.5 ≥ 0.35 → UP 판정 1건
    samples = [_sample(rsi=0.5, bollinger=0.5, momentum=0.5, ret=0.03)]
    report = weight_refit.refit({5: samples}, CURRENT)
    current_row = report.boards[0].current
    assert current_row.n == 1 and current_row.hits == 1
    # 약신호(합산 0.2)는 임계 0.35 미달 → 판정 없음
    weak = [_sample(rsi=0.5, ret=0.03)]
    report2 = weight_refit.refit({5: weak}, CURRENT)
    assert report2.boards[0].current.n == 0


def test_게이트_미달_표본부족이면_승격하지_않는다():
    report = weight_refit.refit({5: _up_samples(99, 1.0)}, CURRENT)
    assert report.promote is False
    assert report.winner is None
    assert "게이트 통과 후보 0개" in report.reasons[0]


def test_게이트_미달_기준선을_못_이기면_승격하지_않는다():
    # n은 충분하지만 적중률 = 기준선(전 표본 동일 판정이라 하한 < 기준선)
    report = weight_refit.refit({5: _up_samples(200, 0.5)}, CURRENT)
    assert report.promote is False


def _selective_samples() -> list[RefitSample]:
    """강신호 고적중 120건 + 무신호 하락 200건 — 신호가 표본을 '고르는' 구조.

    전 표본이 UP이 되면 적중률 = 기준선이라 게이트를 절대 못 넘는다(수학적 성질) —
    후보가 기준선을 이기려면 신호가 좋은 구간만 골라내야 한다.
    """
    strong = [
        _sample(rsi=0.7, bollinger=0.7, momentum=0.7, trend=0.7, obv=0.7,
                ret=0.02 if i < 110 else -0.02)
        for i in range(120)
    ]
    noise = [_sample(ret=-0.02) for _ in range(200)]
    return strong + noise


def test_멱등_최상위가_현행이면_승격하지_않는다():
    # 전 후보가 강신호 120건에서 동률 — 동률 타이브레이크(임계 오름차순·열거 순서)의
    # 최상위(첫 가중치 세트 × 임계 0.25)를 현행으로 두면 멱등이 걸린다.
    current = AnalysisConfig(
        up_threshold=0.25, down_threshold=DOWN_THRESHOLD,
        w_sentiment=0.0, w_rsi=0.4, w_trend=0.0, w_bb=0.4, w_momentum=0.2,
    )
    report = weight_refit.refit({5: _selective_samples()}, current)
    assert report.promote is False
    assert "멱등" in report.reasons[0]
    assert report.winner is not None and report.winner.is_current


def test_승격_게이트_전부_통과():
    # 현행(임계 0.35)은 강신호(합산 0.32)를 놓쳐 n=0 — 임계를 낮춘 후보가
    # 강신호 120건(적중 110)을 골라내 기준선을 뚜렷이 이긴다.
    # 선택 구간 120종목(적중 110) + 표본 외 구간(최근 14일) 30종목(적중 25) — 날짜가 있어야 ④를 통과한다
    samples = _dated_universe(120, 110, first_day=40) + _dated_universe(30, 25, first_day=3)
    report = weight_refit.refit({5: samples}, CURRENT)
    assert report.promote is True, report.reasons
    assert report.winner_holdout is not None and report.winner_holdout.n_effective == 30
    assert "표본 외" in report.reasons[-1]
    winner = report.winner
    assert winner.n_effective >= 100 and winner.gate_passed and not winner.is_current
    config = report.winner_config()
    assert config.down_threshold == DOWN_THRESHOLD == -1.01  # 하락 무발화(2026-09-17 재검증 미달)
    assert config.w_sentiment == 0.0                # 감성 재적합은 E3의 몫


def test_히스테리시스_마진_미만_개선은_보류한다():
    # 현행이 동률 최상위와 파라미터만 다르고(임계 0.30) 성적이 같으면
    # 하한 개선이 0 < 마진(0.02) — 승격 진동을 막는 보류가 걸린다.
    current = AnalysisConfig(
        up_threshold=0.30, down_threshold=DOWN_THRESHOLD,
        w_sentiment=0.0, w_rsi=0.4, w_trend=0.0, w_bb=0.4, w_momentum=0.2,
    )
    report = weight_refit.refit({5: _selective_samples()}, current)
    assert report.promote is False
    assert "마진" in report.reasons[0]
    assert PROMOTION_MARGIN == 0.02  # 상수 변경은 의도된 결정이어야 한다


def test_게이트는_5일_지평만_보고_20일은_참고_병기():
    strong_20 = _up_samples(200, 0.95)
    report = weight_refit.refit({5: [], 20: strong_20}, CURRENT, gate_horizon=5)
    assert report.promote is False
    assert "표본이 없습니다" in report.reasons[0]
    assert [b.horizon_days for b in report.boards] == [5, 20]  # 게이트 지평이 먼저


def test_payload_왕복_스키마():
    report = weight_refit.refit({5: _up_samples(10, 0.5)}, CURRENT)
    payload = report.to_payload()
    assert payload["gate_horizon"] == 5
    assert payload["promote"] is False
    board = payload["boards"][0]
    assert board["total"] == 10
    assert len(board["rows"]) == 32  # 가중치 8종 × 임계 4종
    row = board["rows"][0]
    assert {"up_threshold", "n", "hits", "wilson_lower", "is_current", "gate_passed"} <= set(row)
    # 리더보드는 Wilson 하한 내림차순
    lowers = [r["wilson_lower"] for r in board["rows"]]
    assert lowers == sorted(lowers, reverse=True)


def test_현행_조합이_후보_열거_밖이어도_재채점된다():
    exotic = AnalysisConfig(
        up_threshold=0.33, down_threshold=DOWN_THRESHOLD,
        w_sentiment=0.0, w_rsi=0.7, w_trend=0.0, w_bb=0.3, w_momentum=0.0,
    )
    report = weight_refit.refit({5: _up_samples(50, 0.8)}, exotic)
    board = report.boards[0]
    assert board.current is not None and board.current.n == 50
    assert not any(r.is_current for r in board.rows)  # 열거 후보 중엔 현행이 없다


def test_기준선은_신호를_낸_종목만으로_만든다():
    """[1]-③ — 신호를 한 번도 안 낸 종목의 기준선이 게이트 비교에 섞이면 안 된다."""
    # AAA: 강신호 120건 중 60%만 적중 / BBB: 신호 무발화(전 원신호 0)인데 전부 상승
    aaa = [
        _sample(rsi=1.0, bollinger=1.0, momentum=1.0, trend=1.0, obv=1.0,
                ret=0.02 if i < 72 else -0.02, ticker="AAA")
        for i in range(120)
    ]
    bbb = [_sample(ret=0.02, ticker="BBB") for _ in range(200)]

    board = weight_refit.refit({5: aaa + bbb}, CURRENT).boards[0]

    # 표시용 pooled 기준선은 BBB까지 섞인 값
    assert abs(board.baseline_up_rate - (72 + 200) / 320) < 1e-9
    # 게이트가 쓰는 후보 기준선은 AAA 자기 값뿐
    fired = [r for r in board.rows if r.n > 0]
    assert fired and all(r.n == 120 for r in fired)
    assert all(abs(r.baseline - 0.6) < 1e-9 for r in fired)



def test_표본_외_구간에서_기준선을_못_넘으면_승격하지_않는다():
    # 선택 구간은 강하지만 최근 14일엔 30종목 전부 빗나감 — 9/1 승격이 9월에 무너진 모양
    samples = _dated_universe(120, 110, first_day=40) + _dated_universe(30, 0, first_day=3)
    report = weight_refit.refit({5: samples}, CURRENT)
    assert report.promote is False
    assert report.reasons[0].startswith("표본 외(최근 14일) 적중")


def test_날짜_없는_표본은_표본_외_검증_불가로_승격하지_않는다():
    strong = [_sample(rsi=0.4, bollinger=0.4, ret=0.02 if i < 110 else -0.02) for i in range(120)]
    noise = [_sample(ret=-0.02) for _ in range(200)]
    report = weight_refit.refit({5: strong + noise}, CURRENT)
    assert report.promote is False
    assert report.reasons[0].startswith("표본 외 검증 불가")


def test_같은_종목_같은_주의_반복_신호는_실효_표본_1건이다():
    # 한 종목이 같은 주 5거래일 연속 발화 = 원표본 5 · 실효 1
    monday = datetime(2026, 8, 3, tzinfo=UTC)
    repeats = [_sample(rsi=0.4, bollinger=0.4, ret=0.02, ticker="COST", as_of=monday + timedelta(days=d)) for d in range(5)]
    other = [_sample(rsi=0.4, bollinger=0.4, ret=-0.02, ticker="MCD", as_of=monday + timedelta(days=7))]
    # 최신 표본을 멀리 두어 위 신호들이 표본 외(최근 14일)가 아니라 선택 구간에 들어가게 한다
    later = [_sample(ret=-0.02, ticker="XOM", as_of=monday + timedelta(days=60))]
    board = weight_refit.refit({5: repeats + other + later}, CURRENT).boards[0]
    row = next(r for r in board.rows if r.up_threshold == 0.25 and r.w_rsi == 0.4 and r.w_bb == 0.4 and r.w_momentum == 0.2)
    assert row.n == 6 and row.n_effective == 2
    assert row.hit_rate == 0.5  # 군집 평균 — 원표본 적중률 5/6이 아니다
