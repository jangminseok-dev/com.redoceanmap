from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AlertEmail:
    """발송할 메일 1통 — 실제 발송은 n8n(Gmail 자격증명 보유)이 한다."""

    to: str
    subject: str
    body: str


@dataclass(frozen=True)
class TelegramMessage:
    """발송할 텔레그램 메시지 1건(I-7) — 실제 발송은 n8n(봇 토큰 보유)이 한다."""

    chat_id: str
    text: str


@dataclass(frozen=True)
class BookmarkAlertReport:
    """스캔 1회 결과 — 메일 목록 + 관측 요약(어드민·로그 판독용)."""

    bookmarks_scanned: int
    symbols_scanned: int
    signals_found: int          # 비중립 신호가 잡힌 (사용자, 종목) 쌍 수
    deduped: int = 0            # 같은 상태 지속으로 발송을 억제한 쌍 수(종목+상권)
    emails: list[AlertEmail] = field(default_factory=list)
    area_bookmarks_scanned: int = 0  # 상권 북마크 수(B1)
    area_updates_found: int = 0      # 분기·등급 상태가 확인된 (사용자, 상권) 쌍 수
    telegrams: list[TelegramMessage] = field(default_factory=list)  # 텔레그램 발송분(I-7)
