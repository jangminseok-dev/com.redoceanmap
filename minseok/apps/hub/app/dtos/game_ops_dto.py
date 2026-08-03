"""게임 운영 계약 — admin(소비)과 game(구현)을 잇는다.

admin이 game의 지갑·주가에 손을 대야 하는데 스포크끼리는 직접 참조가 금지다. 그래서 허브가
계약만 소유한다. **게임 내부 규칙(에포크·틱·이벤트 모델)은 이 계약에 새지 않는다** —
admin은 "누구에게 얼마" · "무엇을 몇 % 밀지"만 말하고, 그것이 어떤 틱에 어떤 이벤트로
들어가는지는 game이 정한다.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class GameWalletSummary:
    """운영 화면이 보는 유저 지갑. 게임 화면의 지갑 응답보다 얇다(포지션 평가 없음)."""

    user_id: int
    exists: bool          # 아직 게임을 시작하지 않았으면 False
    cash_krw: int
    epoch_id: int
    rule_version: str
    open_position_count: int
    ledger_total_krw: int  # 원장 합계 — cash_krw와 같아야 한다(불변식 점검용)


@dataclass(frozen=True)
class CapitalGrantCommand:
    user_id: int
    amount_krw: int   # 음수면 회수
    reason: str       # 원장·감사에 남는다
    granted_by: int   # 관리자 user_id


@dataclass(frozen=True)
class CapitalGrantReceipt:
    user_id: int
    amount_krw: int
    cash_krw: int     # 지급 후 잔고
    epoch_id: int
    game_day: int


@dataclass(frozen=True)
class PriceInterventionCommand:
    """주가 개입 지시. 퍼센트 또는 목표가 중 하나를 쓴다.

    `target_price_krw`가 주어지면 game이 현재가를 읽어 `shock_pct`로 환산한다 —
    "이 종목을 10만원으로"가 관리자에게 자연스러운 입력이기 때문이다.
    """

    scope: str                      # symbol | sector | market
    target: str                     # 종목 코드 · 묶음 업종명 · "" (시장 전체)
    shock_pct: float                # 즉시 충격(%)
    drift_pct_per_day: float        # 지속 드리프트(%/게임일)
    duration_days: int
    headline: str                   # 유저에게 보이는 문구 — 일반 뉴스와 구분되지 않는다
    note: str | None                # 관리자 메모(비공개)
    created_by: int
    target_price_krw: int | None = None  # 주어지면 shock_pct를 여기서 역산한다


@dataclass(frozen=True)
class PriceInterventionRecord:
    id: int
    epoch_id: int
    scope: str
    target: str
    target_name: str
    from_tick: int
    from_game_day: int
    shock_pct: float
    drift_pct_per_day: float
    duration_days: int
    headline: str
    note: str | None
    created_by: int
    in_effect: bool  # 지금도 가격에 기여하고 있는가(이벤트 창 안인가)


@dataclass(frozen=True)
class GameSymbolBrief:
    """개입 대상을 고르기 위한 최소 정보. 운영 화면의 선택지 목록이다."""

    symbol: str
    name: str
    sector_group: str
    price_krw: int
    meme: bool
