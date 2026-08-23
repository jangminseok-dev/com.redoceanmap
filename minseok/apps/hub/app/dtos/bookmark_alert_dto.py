from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AlertEmail:
    """발송할 메일 1통 — 실제 발송은 n8n(Gmail 자격증명 보유)이 한다."""

    to: str
    subject: str
    body: str


@dataclass(frozen=True)
class BookmarkAlertReport:
    """스캔 1회 결과 — 메일 목록 + 관측 요약(어드민·로그 판독용)."""

    bookmarks_scanned: int
    symbols_scanned: int
    signals_found: int          # 비중립 신호가 잡힌 (사용자, 종목) 쌍 수
    deduped: int = 0            # 같은 신호 지속으로 발송을 억제한 쌍 수
    emails: list[AlertEmail] = field(default_factory=list)
