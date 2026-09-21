from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from stock.app.dtos.stock_analysis_dto import StockAnalysis
from stock.app.ports.input.stock_use_case import StockUseCase
from stock.app.ports.output.demand_record_port import DemandRecordPort
from stock.app.ports.output.market_data_port import MarketDataPort
from stock.app.ports.output.news_repository import NewsRepositoryPort
from stock.app.ports.output.forecast_history_port import ForecastHistoryPort
from stock.app.ports.output.sentiment_port import SentimentPort
from stock.app.ports.output.signal_config_port import SignalConfigPort
from stock.domain.entities.analysis_config import AnalysisConfig
from stock.domain.entities.outlook import Direction
from stock.domain.services.bar_completeness import is_daily_bar_complete
from stock.domain.services.indicator_calculator import IndicatorCalculator
from stock.domain.services.outlook_predictor import OutlookPredictor
from stock.domain.services.stock_narrator import narrate
from stock.domain.services.volume_profile import compute_volume_profile
from stock.domain.value_objects.market_values import Symbol
from stock.domain.value_objects.indicators import Indicators
from stock.domain.value_objects.sentiment_score import SentimentScore

logger = logging.getLogger(__name__)

MIN_BASELINE_SAMPLES = 5  # 이 미만이면 서프라이즈 대신 당일 절대값(기존 동작) 사용
# 현재 감성 = 최근 N일 저장 라벨 평균(2026-09-21). 질문마다 LLM에 헤드라인 묶음을 물으면 같은 종목이 1분 사이에
# -0.20 → +0.10으로 바뀌었다(샘플링 + 모델이 헤드라인별 숫자 목록을 돌려줘 파서가 첫 줄만 읽음) — 종목 비교 결론이 뒤집혔다.
# 분석의 지표 입력 = 수집 일봉(2026-09-21). 예측·스냅샷·검증이 전부 수집 일봉 기준인데 분석만 질문마다 야후 2년 이력을 새로 받아
# ① 장중엔 진행 중인 오늘 봉이 끼고(실측: 삼성전자 점수 +0.14 vs -0.17) ② 배당 소급 조정이 달라(KO +0.27 vs +0.20, 장 마감 상태)
# 같은 종목의 방향이 화면마다 갈릴 수 있었다. 최근 520봉이면 전체 이력과 점수가 소수 넷째 자리까지 같다(12-1 모멘텀에 253봉 필요).
ANALYZE_BARS = 520
MAX_BAR_AGE = timedelta(days=7)   # 최신 수집 봉이 이보다 낡으면(수집 중단) 야후로 폴백 — 연휴 최장 공백(추석 + 주말)보다 길게
# 수집분과 벤더 이력이 같은 날 종가에서 이만큼 넘게 다르면 가격 기준이 달라진 것(액면분할 등 — 수집에는 분할 처리가 없다).
# 그대로 이어 붙이면 지표가 망가지므로 그 요청은 벤더 이력으로 계산한다. 배당 소급 조정의 실측 괴리는 최대 2.9%(83종목)였다.
SCALE_MISMATCH = 0.10
RECENT_SENTIMENT_DAYS = 7
MIN_RECENT_SAMPLES = 3    # 이 미만이면 LLM 폴백(라벨이 없는 미수집 종목)


REFERENCE_SIGNAL_ENABLED = False  # 재검증에서 두 구간 모두 통과하면 켠다


class StockInteractor(StockUseCase):
    """주식 분석 대장(오케스트레이터).

    시세·지표·뉴스를 모으고, 뉴스 감성만 LLM(SentimentPort→EXAONE)에 위임한 뒤
    결정론적 예측기로 방향 전망을 낸다. 매매 추천은 하지 않고 구조화된 분석만 반환한다.
    최종 사용자 서술은 소비자(chat)가 담당한다(허브 경유, Phase B 예정).
    """

    def __init__(
        self,
        market_data: MarketDataPort,
        sentiment: SentimentPort,
        predictor: OutlookPredictor,
        config: AnalysisConfig,
        news: NewsRepositoryPort | None = None,
        demand: DemandRecordPort | None = None,
        configs: SignalConfigPort | None = None,
        history: ForecastHistoryPort | None = None,
    ) -> None:
        self._market_data = market_data
        self._sentiment = sentiment
        self._predictor = predictor
        self._config = config          # 활성 조합을 못 읽을 때의 폴백
        self._news = news
        self._demand = demand
        self._configs = configs
        self._history = history
        self._calculator = IndicatorCalculator()

    async def _indicators(self, symbol: Symbol) -> Indicators:
        """지표 — 수집 일봉이 먼저(예측과 같은 입력 = 같은 방향), 미수집·낡은 봉·계산 불가면 시세 벤더로 폴백."""
        if self._history is not None:
            try:
                bars = await self._history.find_recent_daily_bars(symbol.code, ANALYZE_BARS)
                if bars and datetime.now(UTC) - bars[-1].ts <= MAX_BAR_AGE:
                    bars = await self._with_newer_closed_bars(symbol, bars)
                    if bars is not None:
                        return self._calculator.compute(
                            closes=[b.close for b in bars], lows=[b.low for b in bars],
                            highs=[b.high for b in bars], volumes=[float(b.volume) for b in bars],
                        )
            except Exception:
                logger.warning("[stock] 수집 일봉 지표 계산 실패 — 벤더로 폴백: %s", symbol.code, exc_info=True)
        return await self._market_data.indicators(symbol)

    async def _with_newer_closed_bars(self, symbol: Symbol, bars: list) -> list | None:
        """수집 일봉 뒤에, 아직 수집되지 않은 **마감된** 새 봉을 벤더 이력에서 보충한다 — 수집이 늦거나 멈춰도 분석은 최신 마감 봉을 본다.

        벤더 이력은 현재가 조회 때문에 같은 요청에서 이미 받아 둔 것(어댑터 캐시)이라 추가 호출이 없다. 진행 중인 봉은 붙이지 않는다
        (검증 조건 = 마감 일봉, 수집과 같은 완성 규칙). 가격 기준이 어긋났으면(분할 등) None — 호출 측이 벤더 이력으로 계산한다.
        보충에 실패하면 수집분만으로 계산한다(열화 동작).
        """
        try:
            vendor = await self._market_data.daily_bars(symbol)
        except Exception:
            return bars
        last = bars[-1]
        same_day = next((v for v in reversed(vendor) if v.ts == last.ts), None)
        if same_day is not None and same_day.close > 0 and abs(last.close / same_day.close - 1) > SCALE_MISMATCH:
            logger.warning("[stock] 수집 일봉과 벤더 이력의 가격 기준이 다르다(분할?) — 벤더 이력으로 계산: %s", symbol.code)
            return None
        now = datetime.now(UTC)
        newer = [v for v in vendor if v.ts > last.ts and is_daily_bar_complete(v.ticker, v.ts, now)]
        return [*bars, *newer]

    async def _active_config(self) -> AnalysisConfig:
        """예측(forecast)·스냅샷과 **같은 활성 검증 조합**으로 판정한다(2026-09-21).

        예전엔 분석만 코드 상수(검증 조합 0.8배 + 감성 0.2)를 썼다 — 같은 종목이 분석 화면에선 "상승 쪽", 예측에선 "중립"으로 갈렸고,
        얹은 감성 서프라이즈는 재검증에서 무신호였다(같은 날 두 종목 짝 비교 49~50%, 순위상관 0, 월마다 부호가 바뀜 — 두 라벨러 모두).
        포트 미주입(테스트)·조회 실패는 생성자 조합으로 폴백한다.
        """
        if self._configs is None:
            return self._config
        try:
            return (await self._configs.active()).config
        except Exception:
            logger.warning("[stock] 활성 판정 조합 조회 실패 — 폴백 조합 사용", exc_info=True)
            return self._config

    async def analyze(self, symbol: Symbol, name: str | None = None) -> StockAnalysis:
        price = await self._market_data.latest_price(symbol)
        # 시세 확인을 통과한(실존) 심볼만 수요 기록 — 워치리스트 수요 편입의 재료.
        # 기록 실패는 분석에 영향 없음(베스트 에포트).
        if self._demand is not None:
            try:
                await self._demand.record(symbol.code)
            except Exception:
                logger.warning("[stock] 수요 기록 실패: %s", symbol.code, exc_info=True)
        indicators = await self._indicators(symbol)
        headlines = await self._merge_headlines(symbol, name)

        # 현재 감성은 저장된 기사 라벨(최근 7일 평균)이 먼저다 — 같은 시점이면 같은 값이고 질문당 LLM 호출이 하나 준다.
        # 라벨이 모자란 종목(미수집)만 헤드라인 묶음을 LLM에 묻는다(폴백).
        recent, recent_n = await self._sentiment_baseline(symbol, days=RECENT_SENTIMENT_DAYS)
        if recent is not None and recent_n >= MIN_RECENT_SAMPLES:
            sentiment = SentimentScore(value=max(-1.0, min(1.0, recent)))
        else:
            sentiment = await self._sentiment.analyze(headlines)                # LLM 폴백

        # 감성 서프라이즈: 현재 값 − 최근 30일 라벨 평균. 항상 긍정적인 종목의 상시 +를
        # 걸러내고 "평소보다 좋아졌는가"만 신호로 쓴다. 현재 값이 저장 라벨이면 기준선과 같은 라벨러·같은 척도다.
        # 표본 부족·조회 실패는 절대값 폴백(라벨 축적 초기의 자연 열화).
        baseline, baseline_n = await self._sentiment_baseline(symbol)
        surprise: float | None = None
        signal_sentiment = sentiment
        if baseline is not None and baseline_n >= MIN_BASELINE_SAMPLES:
            surprise = max(-1.0, min(1.0, sentiment.value - baseline))
            signal_sentiment = SentimentScore(value=surprise)

        config = await self._active_config()
        outlook = self._predictor.predict(indicators, signal_sentiment, config)  # 순수
        contributions = self._predictor.breakdown(indicators, signal_sentiment, config)
        score = self._predictor.score(contributions)
        # 참고 신호: 백테스트 검증(인샘플+홀드아웃) 통과 조합 — 채점 조건(감성 중립) 그대로 재현
        reference = self._predictor.predict(
            indicators, SentimentScore(value=0.0), AnalysisConfig.rsi_bb_reference()
        )
        # 참고 신호 배지는 2026-09-17 중단 — 81종목 10년을 겹침 보정(유효 표본 ÷5)으로 다시 채점하니 최근 5년 우위 -0.5%p로
        # 검증 기준 미달이었다. 옛 통과(+0.4%p)는 겹치는 5일 창을 독립 표본으로 센 결과였다. 계산식은 재검증용으로 남기고 노출만 끈다.
        _reference_raw = reference.direction is Direction.UP
        reference_up = REFERENCE_SIGNAL_ENABLED and _reference_raw
        insights = narrate(
            outlook, score, contributions, indicators, config, reference_up,
            sentiment_surprise=surprise,
        )

        # 매물대 — 이미 쓰는 MarketDataPort로 일봉을 받아 순수 도메인 서비스로 산출한다.
        # 새 아웃바운드 의존을 만들지 않는다. 조회 실패는 분석을 막지 않는다(베스트 에포트).
        profile = None
        try:
            profile = compute_volume_profile(
                await self._market_data.daily_bars(symbol), price.value
            )
        except Exception:
            logger.warning("[stock] 매물대 산출 실패: %s", symbol.code, exc_info=True)

        logger.info(
            "[stock] %s price=%.2f rsi=%.1f sentiment=%.2f → %s(%.2f)",
            symbol.code, price.value, indicators.rsi, sentiment.value,
            outlook.direction.value, outlook.confidence,
        )
        return StockAnalysis(
            symbol=symbol.code,
            price=price.value,
            direction=outlook.direction.value,
            confidence=outlook.confidence,
            sentiment=sentiment.value,
            sentiment_label=sentiment.label,
            sentiment_baseline=baseline if baseline_n >= MIN_BASELINE_SAMPLES else None,
            sentiment_surprise=surprise,
            rsi=indicators.rsi,
            ma20=indicators.ma20,
            ma50=indicators.ma50,
            support=indicators.support,
            resistance=indicators.resistance,
            atr_pct=indicators.atr_pct,
            bb_percent_b=indicators.bb_percent_b,
            volume_ratio=indicators.volume_ratio,
            obv_slope=indicators.obv_slope,
            momentum_12_1=indicators.momentum_12_1,
            reference_up_signal=reference_up,
            headlines=headlines,
            score=score,
            up_threshold=config.up_threshold,
            down_threshold=config.down_threshold,
            neutral_reason=outlook.neutral_reason,
            signals=contributions,
            insights=insights,
            volume_poc_low=profile.poc_low if profile else None,
            volume_poc_high=profile.poc_high if profile else None,
            volume_poc_share=profile.poc_share if profile else None,
            volume_price_position=profile.price_position if profile else None,
        )

    async def _sentiment_baseline(self, symbol: Symbol, days: int = 30) -> tuple[float | None, int]:
        """최근 N일 라벨 감성 평균(기본 30일 = 기준선) — 조회 실패는 (None, 0)로 열화(베스트 에포트)."""
        if self._news is None:
            return None, 0
        try:
            return await self._news.sentiment_baseline(symbol.code, days=days)
        except Exception:
            logger.warning("[stock] 감성 기준선 조회 실패: %s", symbol.code, exc_info=True)
            return None, 0

    async def _merge_headlines(self, symbol: Symbol, name: str | None) -> list[str]:
        """수집 뉴스(DB, n8n 적재) 우선 + 시세 벤더 뉴스 보조(중복 제거, 최대 8건)."""
        collected: list[str] = []
        if self._news:
            collected = await self._news.recent_titles(name or symbol.code, ticker=symbol.code)
        vendor = await self._market_data.recent_headlines(symbol)
        return (collected + [h for h in vendor if h not in collected])[:8]
