"""stock 앱 계층 예외. HTTP 상태코드 변환은 인바운드 어댑터(라우터)가 맡는다."""


class StockError(Exception):
    """stock 유스케이스 공통 예외."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class MarketDataUnavailableError(StockError):
    """종목 시세 데이터를 찾지 못함(없는 심볼 또는 데이터 부족)."""
