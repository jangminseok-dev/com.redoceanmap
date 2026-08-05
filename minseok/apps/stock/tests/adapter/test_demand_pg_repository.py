"""수요 기록의 티커 표준화 — 같은 종목이 표기 때문에 두 행으로 갈라지면 안 된다.

2026-08-05 실측에서 삼성전자가 005930(6회) + 005930.KS(1회)로 쪼개져 있었다.
이 수치는 워치리스트 자동 편입(screen_us_undervalued)의 입력이라 순위가 어긋난다.
"""
from stock.adapter.outbound.pg.demand_pg_repository import _canonical


def test_거래소_접미를_벗겨_한_종목으로_모은다():
    assert _canonical("005930.KS") == "005930"
    assert _canonical("005930") == "005930"
    assert _canonical("035720.KQ") == "035720"


def test_공백과_소문자를_정리한다():
    assert _canonical("  tsla  ") == "TSLA"
    assert _canonical("005930.ks") == "005930"


def test_점이_있는_미국_티커는_건드리지_않는다():
    # 무조건 첫 '.'에서 자르면 클래스 표기가 망가진다 — 알려진 거래소 접미만 벗긴다.
    assert _canonical("BF.B") == "BF.B"
    assert _canonical("BRK-B") == "BRK-B"
