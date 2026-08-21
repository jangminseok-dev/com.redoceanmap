"""weight_refit — 재채점 산식·승격 게이트·히스테리시스·멱등 검증."""
from stock.domain.entities.analysis_config import AnalysisConfig
from stock.domain.services import weight_refit
from stock.domain.services.weight_refit import (
    DOWN_THRESHOLD,
    PROMOTION_MARGIN,
    RefitSample,
)

CURRENT = AnalysisConfig.forecast_signal()  # RSI+BB+MOM 0.4/0.4/0.2 ±0.35


def _sample(rsi=0.0, bollinger=0.0, momentum=0.0, trend=0.0, obv=0.0, ret=0.01) -> RefitSample:
    return RefitSample(
        signals={
            "sentiment": 0.0, "rsi": rsi, "trend": trend,
            "bollinger": bollinger, "obv": obv, "momentum": momentum,
        },
        realized_return_pct=ret,
    )


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
    strong = [
        _sample(rsi=0.4, bollinger=0.4, ret=0.02 if i < 110 else -0.02)
        for i in range(120)
    ]
    noise = [_sample(ret=-0.02) for _ in range(200)]
    report = weight_refit.refit({5: strong + noise}, CURRENT)
    assert report.promote is True
    winner = report.winner
    assert winner.n >= 100 and winner.gate_passed and not winner.is_current
    config = report.winner_config()
    assert config.down_threshold == DOWN_THRESHOLD  # 하락 무발화 유지
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
