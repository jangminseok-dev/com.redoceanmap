"""가격 도달 알림 조립([6]) — 결정론 템플릿, LLM 미사용(bookmark_alert_composer와 동일 규범).

어휘 규범: **사용자가 직접 정한 가격의 도달 '사실' 통지까지만**이다. 이 알림은 예측이
아니고, 조건을 정한 주체가 사용자라 자문에도 해당하지 않는다 — 그 성격이 문장에
드러나야 한다. 매수·매도 권유·다음 방향 전망을 쓰지 않는다. 순수 함수, 표준 라이브러리만.
"""
from __future__ import annotations

from dataclasses import dataclass

_DIRECTION_LABELS = {"above": "이상", "below": "이하"}

PRICE_DISCLAIMER = (
    "이 알림은 회원님이 직접 설정한 가격 조건의 도달 사실 통지이며 "
    "매수·매도 권유가 아닙니다. 투자 판단의 책임은 본인에게 있습니다."
)


def _format_price(ticker: str, value: float) -> str:
    """원화는 정수, 그 외(달러 등)는 소수 2자리 — 채팅 숫자 포매팅 원칙(1-5)과 동일."""
    korean = ticker.split(".")[0].isdigit()
    return f"{value:,.0f}원" if korean else f"{value:,.2f}달러"


@dataclass(frozen=True)
class PriceAlertLine:
    """알림 한 줄의 재료 — 인터랙터가 조건×최신 종가에서 내려 만든다."""

    ticker: str
    target_price: float
    direction: str  # above | below
    price: float    # 판정에 쓴 최신 수집 종가


def compose_price_alert(lines: list[PriceAlertLine]) -> tuple[str, str]:
    """(제목, 본문). 입력 순서 그대로 — 순위 매김은 권유로 읽힌다(bookmark 선례)."""
    subject = f"[redoceanmap] 설정 가격 도달 {len(lines)}건"
    rows = [
        f"- {line.ticker}: 설정선 {_format_price(line.ticker, line.target_price)}"
        f"({_DIRECTION_LABELS.get(line.direction, line.direction)}) 도달"
        f" — 최근 수집가 {_format_price(line.ticker, line.price)}"
        for line in lines
    ]
    body = (
        "설정해 두신 가격 조건에 도달했습니다."
        " (수집 주기 기준 — 실시간이 아니며 최대 1시간가량 늦을 수 있습니다)\n\n"
        + "\n".join(rows)
        + "\n\n이 조건은 1회 통지 후 자동으로 꺼집니다."
        " 다시 받으려면 프로필에서 새 조건을 등록하세요.\n\n"
        + PRICE_DISCLAIMER
    )
    return subject, body
