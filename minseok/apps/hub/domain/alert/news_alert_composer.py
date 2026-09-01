"""티커 뉴스 알림 조립(B9) — 결정론 템플릿, LLM 미사용(bookmark_alert_composer와 동일 규범).

어휘 규범: **수집된 기사와 감성 라벨의 '관측' 안내까지만**. 기사 해석·전망·매매 권유를
쓰지 않는다. 차별점(SAVE 대조)은 "떴다"에 감성 라벨과 현재 신호 상태를 병기하는 것 —
신호 상태는 관측값이지 예측이 아님을 문장이 유지한다. 순수 함수, 표준 라이브러리만.
"""
from __future__ import annotations

from dataclasses import dataclass

_DIRECTION_LABELS = {"UP": "상승 신호", "DOWN": "하락 신호", "NEUTRAL": "중립"}

NEWS_DISCLAIMER = (
    "감성 라벨은 수집 기사 제목에 대한 자동 분류이며 기사·종목에 대한 판단이 아닙니다. "
    "매수·매도 권유가 아니며 투자 판단의 책임은 본인에게 있습니다."
)


@dataclass(frozen=True)
class NewsAlertLine:
    """알림 한 줄의 재료 — 인터랙터가 뉴스×북마크×신호 상태에서 내려 만든다."""

    ticker: str
    title: str
    sentiment: float
    event_type: str | None
    published: str | None      # "8/31" — 발행일 미상은 None
    direction: str | None      # 현재 신호 상태(스냅샷 부재는 None — 라인에서 생략)


def compose_news_alert(lines: list[NewsAlertLine]) -> tuple[str, str]:
    """(제목, 본문). 입력 순서 그대로 — 순위 매김은 권유로 읽힌다(bookmark 선례)."""
    good = sum(1 for line in lines if line.sentiment > 0)
    bad = sum(1 for line in lines if line.sentiment < 0)
    parts = []
    if good:
        parts.append(f"호재성 {good}")
    if bad:
        parts.append(f"악재성 {bad}")
    subject = f"[redoceanmap] 관심 종목 뉴스 {len(lines)}건 ({' · '.join(parts)})"

    rows = []
    for line in lines:
        tone = "호재성" if line.sentiment > 0 else "악재성"
        tags = [f"감성 {line.sentiment:+.1f}({tone})"]
        if line.event_type:
            tags.append(line.event_type)
        if line.published:
            tags.append(f"발행 {line.published}")
        row = f"- {line.ticker} [{' · '.join(tags)}] {line.title}"
        if line.direction and line.direction in _DIRECTION_LABELS:
            row += f"\n  현재 신호 상태: {_DIRECTION_LABELS[line.direction]} (일일 관측 기준)"
        rows.append(row)

    body = (
        "찜해둔 종목에 감성이 강한 뉴스가 수집됐습니다. (수집·라벨링 주기 기준 — 속보 아님)\n\n"
        + "\n".join(rows)
        + "\n\n기사 전문과 근거는 redoceanmap 종목 화면에서 확인하세요.\n\n"
        + NEWS_DISCLAIMER
    )
    return subject, body
