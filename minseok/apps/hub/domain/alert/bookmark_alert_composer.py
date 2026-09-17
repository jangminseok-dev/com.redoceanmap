"""관심 종목 알림 메일 조립(③-M3) — 결정론 템플릿, LLM 미사용.

알림은 신뢰성이 본체라 문장을 생성하지 않는다 — 같은 입력이면 항상 같은 메일.
어휘 규범(이메일 온톨로지와 같은 위상): **신호 '관측' 안내까지만**이다. 매수·매도 권유,
확률 단정을 쓰지 않고 책임 고지를 항상 포함한다(주식 답변 규칙과 동일 경계).
순수 함수 — 표준 라이브러리만(도메인 순수성).
"""
from __future__ import annotations

from dataclasses import dataclass

_DIRECTION_LABELS = {"UP": "반등 신호(과매도)", "DOWN": "조정 신호(과열)"}

DISCLAIMER = (
    "이 메일은 신호 관측 안내이며 매수·매도 권유가 아닙니다. "
    "투자 판단의 책임은 본인에게 있습니다."
)


@dataclass(frozen=True)
class AlertLine:
    """알림 한 줄의 재료 — 인터랙터가 허브 DTO(StockStatusInfo)에서 내려 만든다."""

    label: str            # 북마크 저장 시점 표시명
    ticker: str
    direction: str        # UP | DOWN (중립은 알림 대상이 아니다 — 호출부가 거른다)
    change_pct: float | None   # 전일 대비 비율(0.02 = +2%)
    signal_date: str      # 신호 기준일 "8/22" — 일일 동결 스냅샷 기준
    reference: bool       # 백테스트 검증 참고 신호 여부


def compose_alert(lines: list[AlertLine]) -> tuple[str, str]:
    """(제목, 본문). 방향이 뚜렷한 순서가 아니라 입력 순서 그대로 — 순위 매김은 권유로 읽힌다."""
    ups = sum(1 for line in lines if line.direction == "UP")
    downs = sum(1 for line in lines if line.direction == "DOWN")
    parts = []
    if ups:
        parts.append(f"상승 {ups}")
    if downs:
        parts.append(f"하락 {downs}")
    subject = f"[redoceanmap] 관심 종목 신호 {len(lines)}건 ({' · '.join(parts)})"

    rows = []
    for line in lines:
        change = (
            f"{line.change_pct * 100:+.1f}%" if line.change_pct is not None else "변동 미상"
        )
        row = (
            f"- {line.label}({line.ticker}): "
            f"{_DIRECTION_LABELS.get(line.direction, line.direction)}"
            f" · 전일 대비 {change} · 신호 {line.signal_date} 기준"
        )
        if line.reference:
            row += " · 검증 참고 신호"
        rows.append(row)

    body = (
        "찜해둔 종목에서 신호가 관측됐습니다. (일일 수집 기준 — 준실시간 아님)\n\n"
        + "\n".join(rows)
        + "\n\n자세한 상태는 redoceanmap 북마크 화면에서 확인하세요.\n\n"
        + DISCLAIMER
    )
    return subject, body


# ── 상권 알림(B1) — 종목과 같은 결정론 템플릿, 어휘만 상권 규범 ─────────────

AREA_DISCLAIMER = (
    "등급은 서울시 공공데이터 기반 참고 지표이며 창업 판단의 책임은 본인에게 있습니다."
)


@dataclass(frozen=True)
class AreaAlertLine:
    """상권 알림 한 줄의 재료 — 인터랙터가 허브 DTO(AreaScoreInfo)에서 내려 만든다."""

    label: str              # 북마크 저장 시점 상권 표시명
    quarter_label: str      # "2025년 4분기" — 반영된 데이터 기준 분기
    grade: str              # 우수 | 양호 | 보통 | 주의 | 위험
    total: float            # 종합점수(0~100, 50=서울 평균)
    prev_grade: str | None  # 직전 통지 등급 — 등급이 바뀌었을 때만(같으면 None)


def compose_area_alert(lines: list[AreaAlertLine]) -> tuple[str, str]:
    """(제목, 본문). 입력 순서 그대로 — 순위 매김은 권유로 읽힌다(종목 규칙 승계)."""
    changed = sum(1 for line in lines if line.prev_grade)
    suffix = f" (등급 변동 {changed})" if changed else ""
    subject = f"[redoceanmap] 관심 상권 업데이트 {len(lines)}건{suffix}"

    rows = []
    for line in lines:
        row = (
            f"- {line.label}: {line.quarter_label} 데이터 반영"
            f" · 종합 {line.total:.0f}점 '{line.grade}' (50점=서울 평균)"
        )
        if line.prev_grade:
            row += f" · 직전 통지 '{line.prev_grade}' → '{line.grade}'"
        rows.append(row)

    body = (
        "찜해둔 상권에 새 분기 데이터가 반영되었거나 등급이 바뀌었습니다."
        " (서울시 분기 공공데이터 기준)\n\n"
        + "\n".join(rows)
        + "\n\n자세한 지표는 redoceanmap 지도에서 상권을 확인하세요.\n\n"
        + AREA_DISCLAIMER
    )
    return subject, body
