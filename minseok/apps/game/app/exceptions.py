"""game 앱 계층 예외. HTTP 변환은 라우터가 맡는다(계층 계약)."""
from __future__ import annotations


class GameError(Exception):
    """game 앱 공통 예외."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class InvalidTickRange(GameError):
    """요청한 틱 구간이 허용 범위를 벗어났다 — 미래 틱 조회 포함(game-harness §1-6)."""


class UnknownSymbol(GameError):
    """게임에 없는 종목이다."""


class InsufficientCash(GameError):
    """투자 가능 현금이 모자란다. 최소 생활자금은 쓸 수 없다(trading_rules)."""


class InvalidOrder(GameError):
    """수량·방향이 잘못됐다."""


class PositionNotFound(GameError):
    """포지션이 없거나 남의 것이거나 이미 청산됐다."""


class SeasonClosed(GameError):
    """시즌이 끝나 더 이상 매매할 수 없다. 기록은 읽기 전용으로 남는다."""


class AreaProfileUnavailable(GameError):
    """상권·업종 조합의 실데이터가 없다. 없는 상권이거나 없는 업종이다."""


class StoreNotFound(GameError):
    """가게가 없거나 남의 것이다."""


class InvalidPost(GameError):
    """토론방 글·댓글 본문이 비었거나 길이 상한을 넘었다."""


class PostNotFound(GameError):
    """글·댓글이 없거나 남의 것이거나 이미 내려갔다.

    셋을 구분하지 않는 이유: 남의 글을 지우려 했을 때 "권한 없음"과 "없음"을 나눠 답하면
    글 존재 여부가 새어 나간다.
    """
