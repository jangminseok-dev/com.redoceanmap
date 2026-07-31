from pydantic import BaseModel, Field


class RulebookSchema(BaseModel):

    id: int = Field(0, description="Agent ID")
    name: str = Field("게임 (game)", description="Rulebook's name")
    # 모의 투자 + 상권 창업 시뮬레이션 — 주가는 가상, 상권 매출은 실데이터 기반

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 12,
                "name": "게임 (game)",
            }
        }
    }


class RulebookResponseSchema(BaseModel):

    id: int
    name: str
    introduction: str
    epochId: int = Field(description="시즌 식별자 — 바뀌면 이전 시즌 기록은 읽기 전용")
    ruleVersion: str
    tick: int = Field(description="에포크 기준 현재 틱(1틱 = 60초)")
    gameDay: int
    gameQuarter: int = Field(description="1~8")
    dayOfQuarter: int = Field(description="1~90")
    seasonOver: bool
    ticksRemaining: int
    initialCashKrw: int
    reservedCashKrw: int = Field(description="투자에 쓸 수 없는 최소 생활자금")
    feeRate: float = Field(description="체결당 수수료율")
    shortCarryRatePerGameDay: float = Field(description="숏 보유비용 (게임 1일당)")
    ticksPerGameDay: int
