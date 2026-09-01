from __future__ import annotations

import logging

from hub.app.dtos.bookmark_alert_dto import AlertEmail, TelegramMessage
from hub.app.dtos.price_alert_scan_dto import PriceAlertScanReport
from hub.app.ports.input.price_alert_scan_use_case import PriceAlertScanUseCase
from hub.app.ports.output.member_contact_port import MemberContactPort
from hub.app.ports.output.price_alert_directory_port import PriceAlertDirectoryPort
from hub.app.ports.output.stock_status_port import StockStatusPort
from hub.domain.alert.price_alert_composer import PriceAlertLine, compose_price_alert

logger = logging.getLogger(__name__)


class PriceAlertScanInteractor(PriceAlertScanUseCase):
    """가격 도달 알림 대장([6]) — 교차 도메인 조합이라 허브가 소유한다.

    recommendation(활성 조건·텔레그램)× stock(최신 수집 종가)× auth(회원 이메일)를
    포트로만 조합한다. 발송은 n8n — 여기는 조립까지다(bookmark_alert와 동일 분업).

    - 판정: above → 종가 ≥ 설정선, below → 종가 ≤ 설정선. 봉이 없는 심볼은 건너뛴다
      (다음 스캔 재시도 — 오류 아님).
    - **dedupe = one-shot**: 통지한 조건은 mark_triggered로 즉시 비활성화된다.
      `user_alert_deliveries`를 쓰지 않는 이유는 포트 docstring 참조(전체 교체 충돌).
    - 채널이 하나도 없는 회원의 도달 조건은 **비활성화하지 않는다** — 채널이 생기면
      다음 스캔에서 통지된다(bookmark의 "상태 미기록" 규칙과 같은 결).
    """

    def __init__(
        self,
        alerts: PriceAlertDirectoryPort,
        statuses: StockStatusPort,
        contacts: MemberContactPort,
    ) -> None:
        self._alerts = alerts
        self._statuses = statuses
        self._contacts = contacts

    async def scan(self) -> PriceAlertScanReport:
        alerts = await self._alerts.active_alerts()
        if not alerts:
            return PriceAlertScanReport(alerts_scanned=0, symbols_scanned=0, triggered=0)

        symbols = sorted({a.ticker for a in alerts})
        closes = await self._statuses.latest_closes(symbols)

        # 도달 조건을 사용자별로 모은다 — (알림 줄, 성공 시 비활성화할 id) 쌍
        pending: dict[int, list[tuple[PriceAlertLine, int]]] = {}
        for a in alerts:
            price = closes.get(a.ticker)
            if price is None:
                continue  # 봉 없는 심볼 — 판정 불가는 오류가 아니라 보류다
            hit = price >= a.target_price if a.direction == "above" else price <= a.target_price
            if not hit:
                continue
            pending.setdefault(a.user_id, []).append((
                PriceAlertLine(
                    ticker=a.ticker, target_price=a.target_price,
                    direction=a.direction, price=price,
                ),
                a.alert_id,
            ))

        emails: list[AlertEmail] = []
        telegrams: list[TelegramMessage] = []
        triggered_ids: list[int] = []
        if pending:
            users = sorted(pending)
            contacts = await self._contacts.emails_by_ids(users)
            chats = await self._alerts.telegram_chat_ids(users)
            for user_id in users:
                to = contacts.get(user_id)
                chat_id = chats.get(user_id)
                if not to and not chat_id:
                    # 채널 없음 — 비활성화하지 않고 보류(채널이 생기면 다음 스캔에서 통지)
                    logger.info("[price-alert] user=%d 발송 채널 없음 — 보류", user_id)
                    continue
                lines = [line for line, _ in pending[user_id]]
                subject, body = compose_price_alert(lines)
                if to:
                    emails.append(AlertEmail(to=to, subject=subject, body=body))
                if chat_id:
                    telegrams.append(
                        TelegramMessage(chat_id=chat_id, text=f"{subject}\n\n{body}")
                    )
                triggered_ids.extend(alert_id for _, alert_id in pending[user_id])

        if triggered_ids:
            await self._alerts.mark_triggered(triggered_ids)

        logger.info(
            "[price-alert] 조건 %d건·심볼 %d개 스캔 → 도달 %d건 통지(메일 %d·텔레그램 %d)",
            len(alerts), len(symbols), len(triggered_ids), len(emails), len(telegrams),
        )
        return PriceAlertScanReport(
            alerts_scanned=len(alerts),
            symbols_scanned=len(symbols),
            triggered=len(triggered_ids),
            emails=emails,
            telegrams=telegrams,
        )
