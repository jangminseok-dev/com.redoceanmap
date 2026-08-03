from pydantic import BaseModel, Field


class GameWalletResponseSchema(BaseModel):
    """운영 화면이 보는 유저 지갑."""

    user_id: int
    email: str
    exists: bool = Field(description="아직 게임을 시작하지 않았으면 false")
    cash_krw: int
    epoch_id: int
    rule_version: str
    open_position_count: int
    ledger_total_krw: int = Field(description="원장 합계 — cash_krw와 같아야 한다")
    ledger_matches: bool = Field(description="false면 어딘가에서 돈이 샌 것이다")


class GrantCapitalRequestSchema(BaseModel):
    amount_krw: int = Field(description="지급액. 음수면 회수")
    reason: str = Field(min_length=1, max_length=200, description="원장·감사에 남는다")


class GrantCapitalResponseSchema(BaseModel):
    user_id: int
    amount_krw: int
    cash_krw: int = Field(description="지급 후 잔고")
    game_day: int


class SymbolOptionSchema(BaseModel):
    symbol: str
    name: str = Field(description="가상 회사명 — 실재 기업이 아니다")
    sector_group: str
    price_krw: int
    meme: bool


class InterventionSchema(BaseModel):
    id: int
    scope: str = Field(description="symbol | sector | market")
    target: str
    target_name: str
    from_game_day: int
    shock_pct: float
    drift_pct_per_day: float
    duration_days: int
    headline: str = Field(description="유저 화면에는 일반 뉴스로 보인다")
    note: str | None = Field(default=None, description="관리자 메모 — 유저에게 보이지 않는다")
    in_effect: bool = Field(description="지금도 가격에 기여하는가(이벤트 창 안인가)")


class GameOpsBoardSchema(BaseModel):
    symbols: list[SymbolOptionSchema]
    sector_groups: list[str]
    interventions: list[InterventionSchema]
    max_shock_pct: float
    max_drift_pct_per_day: float
    max_duration_days: int


class IntervenePriceRequestSchema(BaseModel):
    """주가 개입 요청. **지금부터 앞으로만** 적용된다 — 과거 주가는 바뀌지 않는다."""

    scope: str = Field(description="symbol | sector | market")
    target: str = Field(default="", description="종목 코드 · 묶음 업종명 · 시장 전체는 빈 문자열")
    shock_pct: float = Field(default=0.0, description="즉시 충격(%)")
    drift_pct_per_day: float = Field(default=0.0, description="지속 드리프트(%/게임일)")
    duration_days: int = Field(default=2, description="드리프트 지속 게임일")
    headline: str = Field(min_length=1, max_length=120, description="유저에게 보일 뉴스 문구")
    note: str | None = Field(default=None, max_length=200, description="관리자 메모(비공개)")
    target_price_krw: int | None = Field(
        default=None, description="주면 shock_pct를 현재가 대비로 역산한다(종목 개입 전용)"
    )
