from stock.domain.value_objects.indicators import Indicators
from stock.domain.value_objects.position_profile import (
    NEUTRAL,
    OVERBOUGHT,
    OVERSOLD,
    PositionProfile,
)


def _ind(rsi: float = 50.0, support: float = 90.0, resistance: float = 110.0) -> Indicators:
    return Indicators(
        rsi=rsi, ma20=100.0, ma50=100.0, support=support, resistance=resistance, atr_pct=0.02
    )


def test_고점_저점_대비_위치():
    p = PositionProfile.from_indicators(_ind(support=80.0, resistance=125.0), base_price=100.0)
    assert abs(p.drawdown_from_high_pct - (-0.2)) < 1e-9   # 125 → 100 = -20%
    assert abs(p.above_support_pct - 0.25) < 1e-9          # 80 → 100 = +25%
    assert p.atr_pct == 0.02


def test_RSI_국면_경계는_신호_계산과_같은_30_70():
    assert PositionProfile.from_indicators(_ind(rsi=30.0), 100.0).rsi_zone == OVERSOLD
    assert PositionProfile.from_indicators(_ind(rsi=30.1), 100.0).rsi_zone == NEUTRAL
    assert PositionProfile.from_indicators(_ind(rsi=69.9), 100.0).rsi_zone == NEUTRAL
    assert PositionProfile.from_indicators(_ind(rsi=70.0), 100.0).rsi_zone == OVERBOUGHT


def test_지지_저항이_0이면_0으로_열화():
    p = PositionProfile.from_indicators(_ind(support=0.0, resistance=0.0), base_price=100.0)
    assert p.drawdown_from_high_pct == 0.0
    assert p.above_support_pct == 0.0
