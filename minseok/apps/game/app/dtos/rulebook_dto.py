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
    # --- 매매 규칙 ---
    # 프론트가 수수료율·예약금을 하드코딩하지 않도록 서버가 실어 보낸다.
    # 규칙이 바뀌면 화면이 자동으로 따라온다(계수 단일 소유 원칙의 프론트 쪽 짝).
    initial_cash_krw: int
    reserved_cash_krw: int
    fee_rate: float
    short_carry_rate_per_game_day: float
    ticks_per_game_day: int
    # 레버리지 규칙 — 프론트가 배율·청산선·만료를 하드코딩하지 않게 서버가 내려준다
    leverage_tiers: tuple[int, ...] = (1,)
    maintenance_margin_ratio: float = 0.0
    leveraged_expiry_ticks: int = 0
    max_leveraged_positions: int = 0
