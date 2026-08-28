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
        """analyze(실시간 질의) 경로 — 뉴스 감성 비중을 0.5에서 0.2로 낮춘 조합(2026-08-28).

        **값의 근거는 임의 조정이 아니라 검증 조합의 스케일 축소다.** 백테스트로 인샘플·홀드아웃
        양쪽을 통과한 `forecast_signal()`의 `(w_rsi, w_bb, w_momentum) = (0.4, 0.4, 0.2)` · `up=0.35`에
        일괄 0.8을 곱하면 `(0.32, 0.32, 0.16)` · `up=0.28`이 된다. 스코어가 선형 가중합이라
        **감성이 0일 때 이 조합의 방향 판정은 검증 조합과 완전히 동일하다**(스케일 불변).
        남은 0.2가 감성 몫이라, 뉴스는 판정을 뒤집는 축이 아니라 ±0.2를 얹는 보정항이 된다.

        `w_trend=0`인 이유: 3차 재채점에서 두 구간 연속 통과한 조합에 추세 축이 없었다.
        MA 배열은 판정에서 빼되 서술(STOCK_ANSWER_PROMPT 1단계)에서는 계속 인용한다.

        감성 가중치를 그냥 낮추기만 하면 안 되는 이유는 `forecast_signal()` docstring 참조 —
        예산이 모자라 임계에 산술적으로 못 미치면 전량 NEUTRAL이 된다(2026-07-30 실측 814건).
        여기서는 지표 예산을 0.8배로 함께 줄여 임계도 같은 비율로 낮췄으므로 그 함정을 피한다.

        회귀 방지: tests/test_analysis_config.py가 "감성 0일 때 forecast_signal()과 방향 동일"을 고정.
        """
        return cls(
            up_threshold=0.28, down_threshold=-0.28,
            w_sentiment=0.2, w_rsi=0.32, w_trend=0.0, w_bb=0.32, w_momentum=0.16,
        )

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
