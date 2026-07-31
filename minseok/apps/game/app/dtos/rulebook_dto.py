from dataclasses import dataclass


@dataclass(frozen=True)
class RulebookQuery:

    id: int
    name: str


@dataclass(frozen=True)
class RulebookResponse:
    """자기소개 + 현재 게임 시각.

    시각을 함께 싣는 이유: 프론트가 첫 진입에 반드시 부르는 엔드포인트가 되어야
    자기소개가 빈 껍데기로 남지 않는다(game-harness §6-②).
    """

    id: int
    name: str
    introduction: str
    # --- 게임 시각 ---
    epoch_id: int
    rule_version: str
    tick: int
    game_day: int
    game_quarter: int
    day_of_quarter: int
    season_over: bool
    ticks_remaining: int
