from dataclasses import dataclass


@dataclass(frozen=True)
class MarketPriceQuery:

    ticks: int  # 반환할 최근 틱 개수
    candle_symbol: str | None = None  # 일봉을 계산할 종목. None이면 계산하지 않는다
    candle_days: int = 7              # 하루당 60틱을 훑으므로 전 종목에 돌리지 않는다


@dataclass(frozen=True)
class PricePoint:

    tick: int
    price_krw: int


@dataclass(frozen=True)
class SymbolPrices:

    symbol: str
    name: str
    sector: str
    sector_group: str       # 묶음 업종 — 섹터 이벤트가 걸리는 단위이자 화면 필터 축
    meme: bool              # 밈 종목 — 변동성이 크고 전용 뉴스가 붙는다
    price_krw: int
    change_pct: float       # 게임 1일 전 대비
    series: tuple[PricePoint, ...]


@dataclass(frozen=True)
class CandleView:
    """게임 1일(60틱) OHLC 봉. 마지막 봉은 진행 중일 수 있다."""

    game_day: int
    open_krw: int
    high_krw: int
    low_krw: int
    close_krw: int
    simulated_volume: int  # 게임 규칙 산출값 — 실제 체결이 아니다


@dataclass(frozen=True)
class MovingAverageView:
    """이동평균선 하나. 표본이 모자란 앞 구간은 `None`이라 차트가 그 구간을 건너뛴다."""

    period: int              # 게임일
    points: tuple[float | None, ...]  # 봉 배열과 같은 길이·같은 순서


@dataclass(frozen=True)
class SignalAxisView:
    """상태 분해 한 축. 점수만 주면 근거가 사라지므로 축과 기여도를 함께 낸다."""

    key: str      # trend | momentum | position | flow | news
    label: str
    value: float  # -1.0 ~ 1.0
    weight: float
    note: str     # 해석 문장 — 예측이 아니다


@dataclass(frozen=True)
class SymbolAnalysisView:
    """선택 종목의 현재 상태 요약. **예측이 아니다**(게임 주가는 브라운 운동+뉴스 충격)."""

    score: float
    label: str
    axes: tuple[SignalAxisView, ...]
    # 근거가 된 지표 원값 — 화면이 숫자를 그대로 보여줄 수 있게 함께 낸다
    rsi: float | None
    percent_b: float | None
    atr_pct: float | None
    volume_ratio: float | None
    obv_slope: float | None
    news_impact_pct: float  # 창 안 뉴스가 지금 가격에 넣고 있는 값(%)
    headline_count: int
    daily_patterns: tuple["ChartPatternView", ...]  # 일봉 축에서 관측된 형태


@dataclass(frozen=True)
class ChartPatternView:
    """틱 곡선에서 관측된 형태. **예측이 아니다.**

    `points`의 인덱스는 `SymbolPrices.series` 배열 위치이므로 화면이 그대로 좌표로 쓴다.
    `confidence`는 이상적 형태와의 기하학적 근접도이며 적중 확률이 아니다.
    """

    name: str
    label: str
    start_index: int
    end_index: int
    confidence: float
    points: tuple[tuple[int, int], ...]  # (series 인덱스, 가격 원)
    note: str


@dataclass(frozen=True)
class SymbolInfo:
    """종목 카드. **지어낸 값을 넣지 않는다** — 게임에 실적 개념이 없어 PER·ROE는 전부 허구가 된다.

    여기 있는 값은 전부 가격 생성 파라미터이거나 그것에서 직접 계산된 것이다.
    """

    symbol: str
    name: str
    sector: str
    sector_group: str
    meme: bool                     # 밈 종목 — σ 배수가 적용된 상태다
    base_price_krw: int            # 시즌 시작가
    game_daily_sigma_pct: float    # 게임 1일 변동성(%) — 배수를 적용한 체감값
    recent_high_krw: int           # 최근 `recent_days` 게임일 고가
    recent_low_krw: int
    recent_days: int


@dataclass(frozen=True)
class MarketEventView:
    """최근 호재·악재. 저장하지 않고 매번 재현한다 — 같은 틱이면 같은 목록이다.

    영향 종목·영향 크기를 함께 싣는다. 이게 없으면 화면은 "이 뉴스가 내 종목에 걸리는지"를
    알 수 없고, 피드의 대부분이 다른 종목 뉴스라 "뉴스가 반영되지 않는다"로 읽힌다.
    """

    tick: int
    scope: str  # symbol | sector | market
    target: str
    target_name: str
    positive: bool
    headline: str
    affected_symbols: tuple[str, ...]  # 이 뉴스가 실제로 가격을 미는 종목들
    expected_impact_pct: float         # 설계된 즉시 충격(%)
    remaining_impact_pct: float        # 현재 틱에 남아 있는 기여(%) — 0에 가까우면 영향 소멸


@dataclass(frozen=True)
class MarketPricesResponse:
    """게임 시세 응답.

    `virtual`은 항상 True다 — 실시세가 아님을 모든 응답이 스스로 밝힌다(game-harness §2).
    """

    virtual: bool
    calibrated: bool        # False면 종목 파라미터가 캘리브레이션 전 잠정값이다
    epoch_id: int
    rule_version: str
    tick: int
    game_day: int
    game_quarter: int
    season_over: bool
    symbols: tuple[SymbolPrices, ...]
    events: tuple[MarketEventView, ...]
    candles: tuple[CandleView, ...]   # candle_symbol을 지정했을 때만 채워진다
    symbol_info: SymbolInfo | None
    patterns: tuple[ChartPatternView, ...]  # 〃 — 선택 종목의 틱 곡선에서 관측된 형태
    moving_averages: tuple[MovingAverageView, ...]  # 〃 — 봉 배열과 인덱스가 맞는다
    rsi: tuple[float | None, ...]                   # 〃 — 〃
    analysis: SymbolAnalysisView | None             # 〃 — 현재 상태 요약(예측 아님)
