"""AI 모의투자 규칙 — 가정치(`assumed_*`) 단일 소유자.

실데이터(`observed_*`)와 구분한다: 여기 값은 검증된 사실이 아니라 **게임 규칙**이다.
바꾸면 리더보드가 통째로 달라지므로 `RULES_VERSION`을 같이 올린다.
"""
from __future__ import annotations

import math

RULES_VERSION = "v1"

assumed_initial_cash_krw = 100_000_000  # 참가 계정 초기 자본
assumed_fee_rate = 0.001  # 체결당 0.1% — 왕복 0.2%
assumed_usdkrw = 1380.0  # 환율 수집이 없다 — 고정 상수, 화면에 고지
assumed_max_position_weight = 0.20  # 종목당 자산 대비 비중 상한
assumed_max_positions = 10  # 동시 보유 종목 상한
assumed_signal_hold_sessions = 5  # 지표 규칙 계정 보유 기간(거래일) — 스냅샷 지평과 같다
assumed_pending_expiry_sessions = 3  # 이 거래일 안에 체결 봉이 없으면 주문 폐기

ACTIONS = ("BUY", "SELL", "SHORT", "COVER")
SIDES = ("LONG", "SHORT")


def is_krw_ticker(ticker: str) -> bool:
    """거래소 접미로 통화를 가른다 — 005930.KS·000660.KQ는 원화, 나머지는 달러."""
    return ticker.upper().endswith((".KS", ".KQ"))


def to_krw(ticker: str, price: float) -> float:
    return price if is_krw_ticker(ticker) else price * assumed_usdkrw


def fee_krw(notional_krw: float) -> float:
    return round(notional_krw * assumed_fee_rate, 2)


def max_quantity(equity_krw: float, cash_krw: float, price_krw: float, weight: float) -> int:
    """비중 상한과 현금 둘 다 만족하는 최대 주수. 0이면 한 주도 못 산다(체결 거부)."""
    if price_krw <= 0:
        return 0
    budget = min(equity_krw * min(weight, assumed_max_position_weight), cash_krw)
    return max(0, math.floor(budget / (price_krw * (1 + assumed_fee_rate))))
