from __future__ import annotations

import logging

from hub.app.dtos.alert_delivery_dto import DeliveredSignal
from hub.app.dtos.bookmark_alert_dto import AlertEmail, BookmarkAlertReport, TelegramMessage
from hub.app.dtos.stock_status_dto import StockStatusInfo
from hub.app.ports.input.bookmark_alert_use_case import BookmarkAlertUseCase
from hub.app.ports.output.alert_delivery_port import AlertDeliveryPort
from hub.app.ports.output.bookmark_directory_port import BookmarkDirectoryPort
from hub.app.ports.output.commercial_data_port import CommercialDataPort
from hub.app.ports.output.member_contact_port import MemberContactPort
from hub.app.ports.output.stock_status_port import StockStatusPort
from hub.domain.alert.bookmark_alert_composer import (
    AlertLine,
    AreaAlertLine,
    compose_alert,
    compose_area_alert,
)

logger = logging.getLogger(__name__)


def _area_state_key(trdar_code: int) -> str:
    """상권 dedupe 키 — 티커 네임스페이스와 충돌하지 않게 접두사를 붙인다("area:1000001")."""
    return f"area:{trdar_code}"


def _area_state(quarter: int, grade: str) -> str:
    """상권 통지 상태 — "20254양호"(분기 5자 + 등급 2자 = 7자).

    `user_alert_deliveries.direction`이 String(8)이라 마이그레이션 없이 이 인코딩으로
    재사용한다(등급은 area_scorer GRADE_BOUNDS의 2자 고정 어휘).
    """
    return f"{quarter}{grade}"


class BookmarkAlertInteractor(BookmarkAlertUseCase):
    """관심 대상 알림 대장(③-M3 + B1) — 교차 도메인 조합이라 허브가 소유한다.

    recommendation(북마크·수신 설정·발송 상태) × stock(동결 스냅샷 신호) ×
    market(상권 분기·등급) × auth(회원 이메일)를 포트로만 조합한다.
    발송은 n8n(Gmail 자격증명 보유) — 여기는 조립까지다.

    - **종목**(③-M3): 비중립(UP/DOWN) 신호만. 신호 기준은 관심 보드(M7)와 같은 원천
      (StockStatusPort — 일일 스냅샷)이라 메일과 화면이 같은 값을 말한다.
    - **상권**(B1, 2026-08-24): 신규 분기 반영 또는 종합등급 변동. 근거는 chat·지도와
      같은 원천(CommercialDataPort — M3 스코어링)이라 메일과 화면이 같은 등급을 말한다.
      점수 산출 불가 상권은 알림 근거가 없어 침묵한다.

    **dedupe 규칙**: 마지막으로 통지한 (사용자, 대상, 상태)와 같은 상태는 다시 보내지
    않는다. 종목은 방향(UP/DOWN), 상권은 분기+등급("20254양호")이 상태다. 상태가 바뀌면
    새 알림, 신호가 꺼지면(중립·스냅샷/점수 소멸) 상태가 지워져 재발생 때 새 알림이다.
    채널은 이메일 + 텔레그램(I-7, 등록 회원만) — 어느 채널로도 못 보낸 것은 상태에
    남기지 않는다(채널이 생기면 그때 첫 알림).
    """

    def __init__(
        self,
        bookmarks: BookmarkDirectoryPort,
        statuses: StockStatusPort,
        contacts: MemberContactPort,
        deliveries: AlertDeliveryPort,
        market: CommercialDataPort,
    ) -> None:
        self._bookmarks = bookmarks
        self._statuses = statuses
        self._contacts = contacts
        self._deliveries = deliveries
        self._market = market

    async def scan(self) -> BookmarkAlertReport:
        stock_bookmarks = await self._bookmarks.stock_bookmarks()
        area_bookmarks = await self._bookmarks.area_bookmarks()
        if not stock_bookmarks and not area_bookmarks:
            # 관측이 비면 통지 상태도 비운다 — 잔존 상태가 훗날 재등록된 북마크의
            # 첫 알림을 dedupe로 삼키는 것을 막는다
            await self._deliveries.replace([])
            return BookmarkAlertReport(bookmarks_scanned=0, symbols_scanned=0, signals_found=0)

        previous = {
            (s.user_id, s.ticker): s.direction
            for s in await self._deliveries.last_signals()
        }

        by_user: dict[int, list[AlertLine]] = {}   # 종목 — 이번에 새로 알릴 것
        unchanged: list[DeliveredSignal] = []      # 같은 상태 지속 — 발송 없이 상태 유지
        signals_found = 0
        symbols: list[str] = []
        if stock_bookmarks:
            symbols = sorted({b.ticker for b in stock_bookmarks})
            statuses = await self._statuses.latest_statuses(symbols)
            for b in stock_bookmarks:
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

        # 상권(B1) — 분기+등급 상태가 바뀐 북마크만. (알림 줄, 성공 시 기록할 상태) 쌍으로 모은다.
        area_pending: dict[int, list[tuple[AreaAlertLine, DeliveredSignal]]] = {}
        area_updates = 0
        if area_bookmarks:
            quarter = (await self._market.get_area_summary()).latest_quarter
            codes = sorted({b.trdar_code for b in area_bookmarks})
            scores = await self._market.get_area_scores(codes) if quarter else {}
            for b in area_bookmarks:
                score = scores.get(b.trdar_code)
                if quarter is None or score is None:
                    continue  # 점수 산출 불가 상권 — 알림 근거가 없다(상태도 자연 소멸)
                area_updates += 1
                key = (b.user_id, _area_state_key(b.trdar_code))
                state = _area_state(quarter, score.grade)
                if previous.get(key) == state:
                    unchanged.append(DeliveredSignal(
                        user_id=b.user_id, ticker=key[1], direction=state,
                    ))
                    continue
                prev_state = previous.get(key)
                # 이전 상태에서 등급만 떼낸다("20244보통" → "보통") — 등급 변동일 때만 병기
                prev_grade = prev_state[5:] if prev_state else None
                area_pending.setdefault(b.user_id, []).append((
                    AreaAlertLine(
                        label=b.label,
                        quarter_label=f"{str(quarter)[:4]}년 {str(quarter)[4]}분기",
                        grade=score.grade,
                        total=score.total,
                        prev_grade=prev_grade if prev_grade and prev_grade != score.grade else None,
                    ),
                    DeliveredSignal(user_id=b.user_id, ticker=key[1], direction=state),
                ))

        emails: list[AlertEmail] = []
        telegrams: list[TelegramMessage] = []
        delivered: list[DeliveredSignal] = []
        alert_users = sorted(set(by_user) | set(area_pending))
        if alert_users:
            contacts = await self._contacts.emails_by_ids(alert_users)
            chats = await self._bookmarks.telegram_chat_ids(alert_users)
            for user_id in alert_users:
                to = contacts.get(user_id)
                chat_id = chats.get(user_id)
                if not to and not chat_id:
                    # 채널이 하나도 없는 계정(이메일 없음·정지·탈퇴, 텔레그램 미등록) —
                    # 발송 불가는 오류가 아니라 제외다. 상태에도 남기지 않는다.
                    logger.info("[bookmark-alert] user=%d 발송 채널 없음 — 제외", user_id)
                    continue

                def _send(subject: str, body: str) -> None:
                    if to:
                        emails.append(AlertEmail(to=to, subject=subject, body=body))
                    if chat_id:
                        telegrams.append(
                            TelegramMessage(chat_id=chat_id, text=f"{subject}\n\n{body}")
                        )

                if user_id in by_user:
                    subject, body = compose_alert(by_user[user_id])
                    _send(subject, body)
                    delivered.extend(
                        DeliveredSignal(
                            user_id=user_id, ticker=line.ticker, direction=line.direction,
                        )
                        for line in by_user[user_id]
                    )
                if user_id in area_pending:
                    lines = [line for line, _ in area_pending[user_id]]
                    subject, body = compose_area_alert(lines)
                    _send(subject, body)
                    delivered.extend(signal for _, signal in area_pending[user_id])

        # 다음 스캔의 dedupe 기준 = (이번에 보낸 것) + (지속 중이라 안 보낸 것).
        # 꺼진 신호는 여기 없으므로 전체 교체에서 자연히 사라진다.
        await self._deliveries.replace(delivered + unchanged)

        logger.info(
            "[bookmark-alert] 종목 북마크 %d건·종목 %d개, 상권 북마크 %d건 스캔"
            " → 신호 %d건·상권 갱신 %d건(중복 억제 %d)·메일 %d통",
            len(stock_bookmarks), len(symbols), len(area_bookmarks),
            signals_found, area_updates, len(unchanged), len(emails) + len(telegrams),
        )
        return BookmarkAlertReport(
            bookmarks_scanned=len(stock_bookmarks),
            symbols_scanned=len(symbols),
            signals_found=signals_found,
            deduped=len(unchanged),
            emails=emails,
            area_bookmarks_scanned=len(area_bookmarks),
            area_updates_found=area_updates,
            telegrams=telegrams,
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
