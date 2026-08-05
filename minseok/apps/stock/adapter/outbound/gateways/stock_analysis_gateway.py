from __future__ import annotations

from hub.app.dtos.stock_analysis_dto import StockAnalysisResult
from hub.app.ports.output.stock_analysis_port import StockAnalysisPort, StockAnalysisUnavailable
from stock.adapter.outbound.symbol_resolver import resolve_symbol
from stock.app.exceptions import MarketDataUnavailableError
from stock.app.ports.input.stock_use_case import StockUseCase
from stock.domain.value_objects.market_values import Symbol


class StockAnalysisGateway(StockAnalysisPort):
    """허브 StockAnalysisPort 구현 — 질의를 종목 코드로 해석해 stock 유스케이스에 위임한다.

    스포크(chat 등)는 허브 포트만 알고, main.py(합성 루트)가 이 구현을 주입한다.
    stock 앱 계층 예외는 허브 계약 예외(StockAnalysisUnavailable)로 변환한다.
    """

    def __init__(self, use_case: StockUseCase) -> None:
        self._use_case = use_case

    async def analyze(self, query: str) -> StockAnalysisResult:
        try:
            code = await resolve_symbol(query)
            # 원 질의(종목명)를 함께 넘겨 수집 뉴스(DB) 검색에 쓴다.
            analysis = await self._use_case.analyze(Symbol(code=code), name=query)
        except MarketDataUnavailableError as e:
            raise StockAnalysisUnavailable(e.detail)
        return StockAnalysisResult(
            symbol=analysis.symbol,
            price=analysis.price,
            direction=analysis.direction,
            confidence=analysis.confidence,
            sentiment=analysis.sentiment,
            sentiment_label=analysis.sentiment_label,
            rsi=analysis.rsi,
            ma20=analysis.ma20,
            ma50=analysis.ma50,
            support=analysis.support,
            resistance=analysis.resistance,
            headlines=analysis.headlines,
            atr_pct=analysis.atr_pct,
            bb_percent_b=analysis.bb_percent_b,
            volume_ratio=analysis.volume_ratio,
            obv_slope=analysis.obv_slope,
            momentum_12_1=analysis.momentum_12_1,
            reference_up_signal=analysis.reference_up_signal,
            score=analysis.score,
            up_threshold=analysis.up_threshold,
            down_threshold=analysis.down_threshold,
            volume_poc_low=analysis.volume_poc_low,
            volume_poc_high=analysis.volume_poc_high,
            volume_poc_share=analysis.volume_poc_share,
            volume_price_position=analysis.volume_price_position,
        )
