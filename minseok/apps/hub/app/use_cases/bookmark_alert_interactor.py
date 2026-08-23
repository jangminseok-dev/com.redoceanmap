from __future__ import annotations

import logging

from hub.app.dtos.alert_delivery_dto import DeliveredSignal
from hub.app.dtos.bookmark_alert_dto import AlertEmail, BookmarkAlertReport
from hub.app.dtos.stock_status_dto import StockStatusInfo
from hub.app.ports.input.bookmark_alert_use_case import BookmarkAlertUseCase
from hub.app.ports.output.alert_delivery_port import AlertDeliveryPort
from hub.app.ports.output.bookmark_directory_port import BookmarkDirectoryPort
from hub.app.ports.output.member_contact_port import MemberContactPort
from hub.app.ports.output.stock_status_port import StockStatusPort
from hub.domain.alert.bookmark_alert_composer import AlertLine, compose_alert

logger = logging.getLogger(__name__)


class BookmarkAlertInteractor(BookmarkAlertUseCase):
    """관심 종목 알림 대장(③-M3) — 교차 도메인 조합이라 허브가 소유한다.

    recommendation(북마크·수신 설정·발송 상태) × stock(동결 스냅샷 신호) × auth(회원
    이메일)를 포트로만 조합한다. 신호 기준은 관심 보드(M7)와 같은 원천(StockStatusPort —
    일일 스냅샷)이라 메일과 화면이 같은 값을 말한다. 비중립(UP/DOWN)만 알림 대상.
    발송은 n8n(Gmail 자격증명 보유) — 여기는 조립까지다.

    **dedupe 규칙**: 마지막으로 통지한 (사용자, 종목, 방향)과 같은 신호는 다시 보내지
    않는다. 방향이 바뀌면 새 알림, 신호가 꺼지면(중립·스냅샷 소멸) 상태가 지워져 재발생
    때 새 알림이다. 이메일이 없어 발송 못 한 신호는 상태에 남기지 않는다 — 나중에
    이메일이 생기면 그때 첫 알림이 나간다.
    """

    def __init__(
        self,
        bookmarks: BookmarkDirectoryPort,
        statuses: StockStatusPort,
        contacts: MemberContactPort,
        deliveries: AlertDeliveryPort,
    ) -> None:
        self._bookmarks = bookmarks
        self._statuses = statuses
        self._contacts = contacts
        self._deliveries = deliveries

    async def scan(self) -> BookmarkAlertReport:
        bookmarks = await self._bookmarks.stock_bookmarks()
        if not bookmarks:
            # 관측이 비면 통지 상태도 비운다 — 잔존 상태가 훗날 재등록된 북마크의
            # 첫 알림을 dedupe로 삼키는 것을 막는다
            await self._deliveries.replace([])
            return BookmarkAlertReport(bookmarks_scanned=0, symbols_scanned=0, signals_found=0)

        symbols = sorted({b.ticker for b in bookmarks})
        statuses = await self._statuses.latest_statuses(symbols)
        previous = {
            (s.user_id, s.ticker): s.direction
            for s in await self._deliveries.last_signals()
        }

        by_user: dict[int, list[AlertLine]] = {}   # 이번에 새로 알릴 것(dedupe 통과분)
        unchanged: list[DeliveredSignal] = []      # 같은 신호 지속 — 발송 없이 상태 유지
        signals_found = 0
        for b in bookmarks:
            status = statuses.get(b.ticker)
            if status is None or status.direction == "NEUTRAL":
                continue  # 스냅샷 없는 종목·중립은 알림 대상이 아니다(상태도 자연 소멸)
            signals_found += 1
            if previous.get((b.user_id, b.ticker)) == status.direction:
                unchanged.append(DeliveredSignal(
                    user_id=b.user_id, ticker=b.ticker, direction=status.direction,
                ))
                continue  # 이미 통지한 신호가 그대로 — 반복 발송하지 않는다
            by_user.setdefault(b.user_id, []).append(self._to_line(b.label, status))

        emails: list[AlertEmail] = []
        delivered: list[DeliveredSignal] = []
        if by_user:
            contacts = await self._contacts.emails_by_ids(sorted(by_user))
            for user_id in sorted(by_user):
                to = contacts.get(user_id)
                if not to:
                    # 이메일 없는 계정·정지·탈퇴 — 발송 불가는 오류가 아니라 제외다.
                    # 상태에도 남기지 않는다(이메일이 생기면 그때 첫 알림).
                    logger.info("[bookmark-alert] user=%d 이메일 없음 — 발송 제외", user_id)
                    continue
                subject, body = compose_alert(by_user[user_id])
                emails.append(AlertEmail(to=to, subject=subject, body=body))
                delivered.extend(
                    DeliveredSignal(user_id=user_id, ticker=line.ticker, direction=line.direction)
                    for line in by_user[user_id]
                )

        # 다음 스캔의 dedupe 기준 = (이번에 보낸 것) + (지속 중이라 안 보낸 것).
        # 꺼진 신호는 여기 없으므로 전체 교체에서 자연히 사라진다.
        await self._deliveries.replace(delivered + unchanged)

        logger.info(
            "[bookmark-alert] 북마크 %d건·종목 %d개 스캔 → 신호 %d건(중복 억제 %d)·메일 %d통",
            len(bookmarks), len(symbols), signals_found, len(unchanged), len(emails),
        )
        return BookmarkAlertReport(
            bookmarks_scanned=len(bookmarks),
            symbols_scanned=len(symbols),
            signals_found=signals_found,
            deduped=len(unchanged),
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
