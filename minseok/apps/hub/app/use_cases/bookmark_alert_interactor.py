from __future__ import annotations

import logging

from hub.app.dtos.bookmark_alert_dto import AlertEmail, BookmarkAlertReport
from hub.app.dtos.stock_status_dto import StockStatusInfo
from hub.app.ports.input.bookmark_alert_use_case import BookmarkAlertUseCase
from hub.app.ports.output.bookmark_directory_port import BookmarkDirectoryPort
from hub.app.ports.output.member_contact_port import MemberContactPort
from hub.app.ports.output.stock_status_port import StockStatusPort
from hub.domain.alert.bookmark_alert_composer import AlertLine, compose_alert

logger = logging.getLogger(__name__)


class BookmarkAlertInteractor(BookmarkAlertUseCase):
    """관심 종목 알림 대장(③-M3) — 교차 도메인 조합이라 허브가 소유한다.

    recommendation(북마크) × stock(동결 스냅샷 신호) × auth(회원 이메일)를 포트로만
    조합한다. 신호 기준은 관심 보드(M7)와 같은 원천(StockStatusPort — 일일 스냅샷)이라
    메일과 화면이 같은 값을 말한다. 비중립(UP/DOWN)만 알림 대상(기존 signal_scan의
    '중립 제외'와 동일 규칙). 발송은 n8n(Gmail 자격증명 보유) — 여기는 조립까지다.
    v1 한계: 신호가 유지되면 스케줄 주기마다 반복 발송된다(전일 대비 dedupe는 후속).
    """

    def __init__(
        self,
        bookmarks: BookmarkDirectoryPort,
        statuses: StockStatusPort,
        contacts: MemberContactPort,
    ) -> None:
        self._bookmarks = bookmarks
        self._statuses = statuses
        self._contacts = contacts

    async def scan(self) -> BookmarkAlertReport:
        bookmarks = await self._bookmarks.stock_bookmarks()
        if not bookmarks:
            return BookmarkAlertReport(bookmarks_scanned=0, symbols_scanned=0, signals_found=0)

        symbols = sorted({b.ticker for b in bookmarks})
        statuses = await self._statuses.latest_statuses(symbols)

        by_user: dict[int, list[AlertLine]] = {}
        for b in bookmarks:
            status = statuses.get(b.ticker)
            if status is None or status.direction == "NEUTRAL":
                continue  # 스냅샷 없는 종목·중립은 알림 대상이 아니다
            by_user.setdefault(b.user_id, []).append(self._to_line(b.label, status))

        signals_found = sum(len(lines) for lines in by_user.values())
        emails: list[AlertEmail] = []
        if by_user:
            contacts = await self._contacts.emails_by_ids(sorted(by_user))
            for user_id in sorted(by_user):
                to = contacts.get(user_id)
                if not to:
                    # 이메일 없는 계정·정지·탈퇴 — 발송 불가는 오류가 아니라 제외다
                    logger.info("[bookmark-alert] user=%d 이메일 없음 — 발송 제외", user_id)
                    continue
                subject, body = compose_alert(by_user[user_id])
                emails.append(AlertEmail(to=to, subject=subject, body=body))

        logger.info(
            "[bookmark-alert] 북마크 %d건·종목 %d개 스캔 → 신호 %d건·메일 %d통",
            len(bookmarks), len(symbols), signals_found, len(emails),
        )
        return BookmarkAlertReport(
            bookmarks_scanned=len(bookmarks),
            symbols_scanned=len(symbols),
            signals_found=signals_found,
            emails=emails,
        )

    @staticmethod
    def _to_line(label: str, s: StockStatusInfo) -> AlertLine:
        return AlertLine(
            label=label,
            ticker=s.ticker,
            direction=s.direction,
            change_pct=s.change_pct,
            signal_date=f"{s.as_of.month}/{s.as_of.day}",
            reference=s.ready,
        )
