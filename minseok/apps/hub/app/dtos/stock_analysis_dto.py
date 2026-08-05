"""주식 분석 계약 DTO.

허브(hub)가 공개하는 앱 간 협력 계약의 일부. stock(스포크)이 채워서 반환하고
chat(스포크)이 서술 생성에 소비한다. 원시 수치만 담으며(문장화는 소비자 관심사),
외부 의존 없는 순수 객체다.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StockAnalysisResult:
    symbol: str            # 해석된 종목 코드 (예: '005930', 'AAPL')
    price: float
    direction: str         # UP | DOWN | NEUTRAL
    confidence: float      # 0.0 ~ 1.0
    sentiment: float       # -1.0 ~ 1.0
    sentiment_label: str   # 긍정 | 중립 | 부정
    rsi: float
    ma20: float
    ma50: float
    support: float
    resistance: float
    headlines: list[str]
    atr_pct: float = 0.0               # ATR(14)/종가 — 일 변동성 비율
    bb_percent_b: float = 0.5          # 볼린저 %B (0=하단, 1=상단)
    volume_ratio: float = 1.0          # 최근 5일 평균 거래량 / 20일 평균
    obv_slope: float = 0.0             # OBV 20일 정규화 기울기 (수급 방향)
    momentum_12_1: float = 0.0         # 12-1 모멘텀 (이력 부족 시 0.0)
    reference_up_signal: bool = False  # 백테스트 검증 통과 RSI+BB ±0.35 UP 참고 신호 — 확률 아님
    score: float = 0.0                 # 가중 합산 종합 점수 (-1~1) — 신호 세기(약/보통/강) 판정용
    up_threshold: float = 0.3          # 방향 판정 기준 (프론트 strength()와 동일 공식)
    down_threshold: float = -0.3
    # 매물대(거래 밀집 구간) — 과거에 어느 가격대에서 많이 거래됐나. 산출 불가면 None.
    # **지지/저항이 아니다.** 위 support/resistance는 출처가 다른 별개 지표이고,
    # 매물대를 지지선으로 환원하는 주장은 검증된 바 없다(프론트 차트 규칙 그대로 승계).
    volume_poc_low: float | None = None
    volume_poc_high: float | None = None
    volume_poc_share: float | None = None      # POC 구간이 전체 거래량에서 차지하는 비율(0~1)
    volume_price_position: str | None = None   # 현재가와 POC의 관계: above | inside | below
