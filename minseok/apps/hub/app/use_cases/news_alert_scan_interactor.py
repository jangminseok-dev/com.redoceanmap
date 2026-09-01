from __future__ import annotations

import logging

from hub.app.dtos.bookmark_alert_dto import AlertEmail, TelegramMessage
from hub.app.dtos.news_alert_dto import NewsAlertScanReport
from hub.app.ports.input.news_alert_scan_use_case import NewsAlertScanUseCase
from hub.app.ports.output.bookmark_directory_port import BookmarkDirectoryPort
from hub.app.ports.output.member_contact_port import MemberContactPort
from hub.app.ports.output.news_alert_feed_port import NewsAlertFeedPort
from hub.app.ports.output.stock_status_port import StockStatusPort
from hub.domain.alert.news_alert_composer import NewsAlertLine, compose_news_alert

logger = logging.getLogger(__name__)

# 알림 가치가 있는 감성 하한(B9 — ROADMAP §SAVE 대조의 제안 임계 그대로).
# 중립·약한 감성까지 보내면 30분 수집 주기에서 알림이 소음이 된다.
MIN_ABS_SENTIMENT = 0.5


class NewsAlertScanInteractor(NewsAlertScanUseCase):
    """티커 뉴스 알림 대장(B9) — 교차 도메인 조합이라 허브가 소유한다.

    stock(커서 이후 강한 감성 뉴스)× recommendation(북마크·텔레그램)× auth(이메일)를
    포트로만 조합한다. 발송은 n8n — 여기는 조립까지다(bookmark_alert와 동일 분업).

    - **dedupe = 피드 커서**: NewsAlertFeedPort가 마지막 처리 지점 이후만 내준다
      (같은 뉴스가 두 번 나오지 않는 것이 포트 계약 — at-most-once).
    - 차별점(SAVE 대조): "떴다"만이 아니라 감성 라벨 + 현재 신호 상태를 병기한다.
      신호 상태는 스냅샷 관측값이고, 없으면 라인에서 생략(열화 동작).
    - 티커 매칭은 거래소 접미를 벗겨 비교한다(005930 ↔ 005930.KS —
      StockStatusPort 구현이 흡수하는 것과 같은 변형).
    """

    def __init__(
        self,
        feed: NewsAlertFeedPort,
        bookmarks: BookmarkDirectoryPort,
        statuses: StockStatusPort,
        contacts: MemberContactPort,
    ) -> None:
        self._feed = feed
        self._bookmarks = bookmarks
        self._statuses = statuses
        self._contacts = contacts

    async def scan(self) -> NewsAlertScanReport:
        items = await self._feed.pull_alertable(MIN_ABS_SENTIMENT)
        if not items:
            return NewsAlertScanReport(articles_found=0, bookmarks_matched=0)

        stock_bookmarks = await self._bookmarks.stock_bookmarks()
        holders: dict[str, list[int]] = {}  # 접미 제거 티커 → 북마크한 사용자들
        for b in stock_bookmarks:
            holders.setdefault(_base(b.ticker), []).append(b.user_id)

        matched_symbols = sorted({
            item.ticker for item in items if _base(item.ticker) in holders
        })
        statuses = (
            await self._statuses.latest_statuses(matched_symbols) if matched_symbols else {}
        )

        by_user: dict[int, list[NewsAlertLine]] = {}
        matched = 0
        for item in items:
            users = holders.get(_base(item.ticker))
            if not users:
                continue
            status = statuses.get(item.ticker)
            line = NewsAlertLine(
                ticker=item.ticker,
                title=item.title,
                sentiment=item.sentiment,
                event_type=item.event_type,
                published=(
                    f"{item.published_at.month}/{item.published_at.day}"
                    if item.published_at else None
                ),
                direction=status.direction if status else None,
            )
            for user_id in sorted(set(users)):
                matched += 1
                by_user.setdefault(user_id, []).append(line)

        emails: list[AlertEmail] = []
        telegrams: list[TelegramMessage] = []
        if by_user:
            users = sorted(by_user)
            contacts = await self._contacts.emails_by_ids(users)
            chats = await self._bookmarks.telegram_chat_ids(users)
            for user_id in users:
                to = contacts.get(user_id)
                chat_id = chats.get(user_id)
                if not to and not chat_id:
                    # 채널 없음 — 제외. 커서는 이미 전진했으므로 이 뉴스는 다시 안 온다
                    # (뉴스는 신호와 달리 지속 상태가 아니라 보류 재시도 의미가 없다).
                    logger.info("[news-alert] user=%d 발송 채널 없음 — 제외", user_id)
                    continue
                subject, body = compose_news_alert(by_user[user_id])
                if to:
                    emails.append(AlertEmail(to=to, subject=subject, body=body))
                if chat_id:
                    telegrams.append(
                        TelegramMessage(chat_id=chat_id, text=f"{subject}\n\n{body}")
                    )

        logger.info(
            "[news-alert] 후보 뉴스 %d건 → 매칭 %d쌍·메일 %d·텔레그램 %d",
            len(items), matched, len(emails), len(telegrams),
        )
        return NewsAlertScanReport(
            articles_found=len(items),
            bookmarks_matched=matched,
            emails=emails,
            telegrams=telegrams,
        )


def _base(ticker: str) -> str:
    """거래소 접미 제거("005930.KS" → "005930") — 북마크 키와 뉴스 티커의 공통 분모."""
    return ticker.split(".")[0].upper()
