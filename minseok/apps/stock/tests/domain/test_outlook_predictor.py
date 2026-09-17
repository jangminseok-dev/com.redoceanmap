from stock.domain.entities.analysis_config import AnalysisConfig
from stock.domain.entities.outlook import Direction
from stock.domain.services.outlook_predictor import OutlookPredictor
from stock.domain.value_objects.indicators import Indicators
from stock.domain.value_objects.sentiment_score import SentimentScore


def _ind(rsi: float = 50.0, ma20: float = 100.0, ma50: float = 100.0) -> Indicators:
    return Indicators(rsi=rsi, ma20=ma20, ma50=ma50, support=90.0, resistance=110.0)


def test_감성은_지표를_보정할_뿐_단독으로_방향을_만들지_않는다():
    """뉴스 비중 축소(2026-08-28)의 핵심 동작 — 감성은 지표가 문턱 근처일 때만 방향을 굳힌다.

    이전 default()는 감성 가중치가 0.5여서 긍정 뉴스 하나로 UP이 나왔다. 지금은 0.2라
    지표가 이미 문턱 가까이 와 있어야 감성이 결정적일 수 있다.
    """
    predictor = OutlookPredictor()
    config = AnalysisConfig.default()
    # 밴드 하단 근처(%B 0.25) — 지표만으로는 문턱(0.28)에 못 미친다
    near = Indicators(
        rsi=50.0, ma20=100.0, ma50=100.0, support=90.0, resistance=110.0, bb_percent_b=0.25,
    )
    assert predictor.predict(near, SentimentScore(0.0), config).direction is Direction.NEUTRAL

    out = predictor.predict(near, SentimentScore(0.8), config)
    assert out.direction is Direction.UP
    assert 0.0 < out.confidence <= 1.0


def test_negative_sentiment_and_overbought_no_longer_predicts_down():
    """과매수 + 악재 뉴스여도 하락 방향은 나오지 않는다(2026-09-17 하락 무발화 복귀 — AnalysisConfig 참조).

    아래는 8/28 당시의 조정 기록이다.

    두 번 조정됐다(2026-08-28). ① 감성 가중치가 0.5→0.2로 낮아져 약한 과매수는 뉴스가
    나빠도 문턱에 닿지 않는다. ② 하락 문턱이 검증값 -0.45의 0.8배인 **-0.36**으로 내려가
    (이전 -0.28은 미검증 대칭값), rsi=85 단독(-0.32)으로는 이제 부족하다.

    지표가 주도하고 뉴스가 보조한다는 구조가 여기서 그대로 보인다 — 감성 -0.8이 얹는 몫은
    -0.16뿐이라, 지표가 이미 문턱 가까이 와 있어야 방향이 굳는다.
    """
    predictor = OutlookPredictor()
    # rsi 90(-0.373): 8/28 정책에선 문턱을 넘었지만 이제 관망
    assert predictor.predict(
        _ind(rsi=90.0), SentimentScore(-0.8), AnalysisConfig.default()
    ).direction is Direction.NEUTRAL

    # rsi 85(-0.32)는 악재 뉴스가 있어도 관망 — 뉴스는 판정을 뒤집지 못한다
    assert predictor.predict(
        _ind(rsi=85.0), SentimentScore(-0.8), AnalysisConfig.default()
    ).direction is Direction.NEUTRAL


def test_flat_signals_predict_neutral():
    out = OutlookPredictor().predict(_ind(), SentimentScore(0.0), AnalysisConfig.default())
    assert out.direction is Direction.NEUTRAL


def test_기본_config는_볼린저와_모멘텀을_쓰고_추세와_OBV는_쓰지_않는다():
    """default()가 검증 조합(RSI+BB+MOM)으로 교체된 뒤의 피처 구성 고정(2026-08-28).

    이전에는 BB·모멘텀 가중치가 0이라 "신규 피처를 무시한다"가 보존 대상이었다. 지금은 반대로
    **그 셋이 판정의 본체**이고, 백테스트에서 기여가 확인되지 않은 추세·OBV가 0이다.
    """
    predictor = OutlookPredictor()
    config = AnalysisConfig.default()
    assert config.w_trend == 0.0
    assert config.w_obv == 0.0

    # 밴드 하단 + 강한 모멘텀 → 감성 없이도 UP (예전 default로는 산술적으로 불가능했다)
    features = Indicators(
        rsi=50.0, ma20=100.0, ma50=100.0, support=90.0, resistance=110.0,
        bb_percent_b=0.0, momentum_12_1=1.0,
    )
    assert predictor.predict(features, SentimentScore(0.0), config).direction is Direction.UP

    # 추세·OBV만 극단이면 방향이 나오지 않는다 — 판정에서 빠진 축이라는 증거
    ignored = Indicators(
        rsi=50.0, ma20=200.0, ma50=100.0, support=90.0, resistance=110.0, obv_slope=5.0,
    )
    assert predictor.predict(ignored, SentimentScore(0.0), config).direction is Direction.NEUTRAL


def test_bb_가중치를_주면_하단_밴드에서_상승_신호():
    config = AnalysisConfig(up_threshold=0.3, down_threshold=-0.3, w_bb=0.5)
    ind = Indicators(
        rsi=50.0, ma20=100.0, ma50=100.0, support=90.0, resistance=110.0, bb_percent_b=0.0,
    )
    out = OutlookPredictor().predict(ind, SentimentScore(0.0), config)
    assert out.direction is Direction.UP


def test_obv_가중치를_주면_수급_순증에서_상승_신호():
    config = AnalysisConfig(up_threshold=0.3, down_threshold=-0.3, w_obv=0.5)
    ind = Indicators(
        rsi=50.0, ma20=100.0, ma50=100.0, support=90.0, resistance=110.0, obv_slope=1.0,
    )
    out = OutlookPredictor().predict(ind, SentimentScore(0.0), config)
    assert out.direction is Direction.UP


def test_momentum_가중치를_주면_강한_상승_모멘텀에서_상승_신호():
    config = AnalysisConfig(up_threshold=0.3, down_threshold=-0.3, w_momentum=0.5)
    ind = Indicators(
        rsi=50.0, ma20=100.0, ma50=100.0, support=90.0, resistance=110.0, momentum_12_1=1.0,
    )
    out = OutlookPredictor().predict(ind, SentimentScore(0.0), config)
    assert out.direction is Direction.UP


def test_volume_confirm_미달이면_방향_신호를_관망으로_강등():
    config = AnalysisConfig(up_threshold=0.3, down_threshold=-0.3, w_bb=1.0, volume_confirm=1.0)
    ind = Indicators(
        rsi=50.0, ma20=100.0, ma50=100.0, support=90.0, resistance=110.0,
        bb_percent_b=0.0, volume_ratio=0.5,  # 강한 UP 신호 + 거래량 평소의 절반
    )
    out = OutlookPredictor().predict(ind, SentimentScore(0.0), config)
    assert out.direction is Direction.NEUTRAL
    assert out.confidence == 0.0


def test_volume_confirm_충족이면_방향_유지():
    config = AnalysisConfig(up_threshold=0.3, down_threshold=-0.3, w_bb=1.0, volume_confirm=1.0)
    ind = Indicators(
        rsi=50.0, ma20=100.0, ma50=100.0, support=90.0, resistance=110.0,
        bb_percent_b=0.0, volume_ratio=1.2,
    )
    out = OutlookPredictor().predict(ind, SentimentScore(0.0), config)
    assert out.direction is Direction.UP


def test_rsi_bb_reference_config는_과매도_밴드하단에서_up():
    ind = Indicators(
        rsi=20.0, ma20=100.0, ma50=100.0, support=90.0, resistance=110.0, bb_percent_b=0.0,
    )
    out = OutlookPredictor().predict(ind, SentimentScore(0.0), AnalysisConfig.rsi_bb_reference())
    assert out.direction is Direction.UP


def test_atr_veto_초과_변동성이면_무조건_관망():
    config = AnalysisConfig(up_threshold=0.3, down_threshold=-0.3, atr_veto=0.03)
    ind = Indicators(
        rsi=10.0, ma20=120.0, ma50=100.0, support=90.0, resistance=110.0, atr_pct=0.08,
    )
    out = OutlookPredictor().predict(ind, SentimentScore(0.9), config)  # 강한 신호에도
    assert out.direction is Direction.NEUTRAL
    assert out.confidence == 0.0
