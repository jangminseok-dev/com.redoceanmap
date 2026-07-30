from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AnalysisConfig:
    """전망 판정 파라미터 — 순수 도메인 엔티티.

    종합 점수가 up_threshold 이상이면 상승, down_threshold 이하면 하락 전망을 낸다.
    신호 가중치(w_*)는 백테스트 스윕으로 조합을 채점하기 위한 손잡이 — 기본값은
    기존 동작(감성 0.5 + RSI 0.3 + MA추세 0.2, 신규 피처 미사용)과 동일하다.
    """

    up_threshold: float
    down_threshold: float
    w_sentiment: float = 0.5
    w_rsi: float = 0.3
    w_trend: float = 0.2
    w_bb: float = 0.0        # 볼린저 %B 평균회귀 신호 가중치
    w_obv: float = 0.0       # OBV 수급 방향 신호 가중치
    w_momentum: float = 0.0  # 12-1 모멘텀(추세 지속) 신호 가중치
    atr_veto: float | None = None  # ATR 비율이 이 값 초과면 관망(NEUTRAL) — 변동성 필터
    volume_confirm: float | None = None  # volume_ratio가 이 값 미만이면 방향 신호를 관망으로 강등 — 거래량 확인 필터

    @classmethod
    def default(cls) -> "AnalysisConfig":
        return cls(up_threshold=0.3, down_threshold=-0.3)

    @classmethod
    def forecast_signal(cls) -> "AnalysisConfig":
        """forecast·예측 스냅샷 슬라이스 전용 — 감성 중립 경로에서 검증된 조합.

        3차 재채점(2026-07-14)의 최우수 신호 RSI+BB+MOM(0.4/0.4/0.2) ±0.35 —
        인샘플 Wilson 하한 +3.5%p·홀드아웃 +0.9%p로 두 독립 구간 모두 통과했고,
        **검증 조건이 감성 중립**이라 감성을 싣지 않는 이 슬라이스와 정합한다.

        `default()`(감성 0.5+RSI 0.3+추세 0.2, ±0.3)를 쓰면 안 되는 이유: 감성 가중치 0.5가
        사장돼 남는 예산이 0.5뿐이고, RSI 신호는 30~70 구간에서 0이라(실측 94%) 도달 가능한
        |score| 상한이 추세의 0.2다 — 임계 0.3에 **산술적으로 못 미쳐 전량 NEUTRAL이 된다**
        (2026-07-30 실측: 스냅샷 814건 전부 NEUTRAL, 최대 |score| 0.2000).

        `down_threshold`는 도달 불가값이다 — `score`가 [-1, 1]로 클램프되므로 DOWN이 발화하지
        않는다. 하락은 방향 라벨이 아니라 실측 분포(`DirectionStats`의 낙폭·회복 통계)로 제시한다:
        재채점 2·3차 모두 **하락 방향은 두 구간 연속 통과 조합이 없었다**(하락 예측 불가).
        근거 → [[minseok/apps/stock/_docs/BACKTEST_RESCORE_2026-07|BACKTEST_RESCORE_2026-07]] 4차.
        """
        return cls(
            up_threshold=0.35, down_threshold=-1.01,
            w_sentiment=0.0, w_rsi=0.4, w_trend=0.0, w_bb=0.4, w_momentum=0.2,
        )

    @classmethod
    def rsi_bb_reference(cls) -> "AnalysisConfig":
        """참고 신호 전용 — 2026-07 재채점에서 인샘플·홀드아웃 양쪽 게이트를 통과한 유일 조합.

        과매도(RSI)+밴드 하단(%B) 평균회귀 UP 신호. 감성 미사용(백테스트 검증 조건과 동일).
        근거: _docs/BACKTEST_RESCORE_2026-07.md — 기본 가중치 승격은 금지, 참고 표시 전용.
        """
        return cls(
            up_threshold=0.35, down_threshold=-0.35,
            w_sentiment=0.0, w_rsi=0.5, w_trend=0.0, w_bb=0.5,
        )
