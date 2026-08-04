"""게임 운영 화면의 레이어 간 전달 객체.

허브 DTO(`hub.app.dtos.game_ops_dto`)를 그대로 쓰지 않는 이유: 허브 계약은 **game과의 계약**이고
이쪽은 **화면과의 계약**이다. 검색 조건(이메일로 유저 찾기)처럼 game이 알 필요 없는 것이 여기
들어오고, 반대로 game 내부 값(epoch·tick)은 화면이 그대로 보여줄 필요가 없다.
"""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GameWalletQuery:
    user_id: int


@dataclass(frozen=True)
class GameWalletView:
    user_id: int
    email: str
    exists: bool
    cash_krw: int
    epoch_id: int
    rule_version: str
    open_position_count: int
    ledger_total_krw: int
    ledger_matches: bool  # 원장 합계 == 잔고. 어긋나면 어딘가에서 돈이 샜다


@dataclass(frozen=True)
class GrantCapitalCommand:
    user_id: int
    amount_krw: int
    reason: str
    granted_by: int


@dataclass(frozen=True)
class GrantCapitalResult:
    user_id: int
    amount_krw: int
    cash_krw: int
    game_day: int


@dataclass(frozen=True)
class SymbolOption:
    symbol: str
    name: str
    sector_group: str
    price_krw: int
    meme: bool


@dataclass(frozen=True)
class InterveneCommand:
    scope: str
    target: str
    shock_pct: float
    drift_pct_per_day: float
    duration_days: int
    headline: str
    note: str | None
    created_by: int
    target_price_krw: int | None = None


@dataclass(frozen=True)
class InterventionView:
    id: int
    scope: str
    target: str
    target_name: str
    from_game_day: int
    shock_pct: float
    drift_pct_per_day: float
    duration_days: int
    headline: str
    note: str | None
    in_effect: bool


@dataclass(frozen=True)
class GameOpsBoard:
    """개입 화면이 한 번에 받는 것 — 대상 목록 + 이력."""

    symbols: tuple[SymbolOption, ...]
    sector_groups: tuple[str, ...]
    interventions: tuple[InterventionView, ...]
    max_shock_pct: float
    max_drift_pct_per_day: float
    max_duration_days: int


@dataclass(frozen=True)
class ReportedContentView:
    """신고 대기줄 한 줄. 작성자는 게임이 만든 가명이며 실명이 아니다."""

    target_type: str
    target_id: int
    symbol: str
    author: str
    body: str
    report_count: int
    reasons: tuple[str, ...]
    reported_at: datetime
    hidden: bool


@dataclass(frozen=True)
class HideContentCommand:
    target_type: str
    target_id: int
    reason: str
