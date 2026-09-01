from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.news_alert_dto import AlertableNews


class NewsAlertFeedPort(ABC):
    """알림 후보 뉴스 피드 계약(B9) — 허브 스캔(소비)과 stock(구현)을 잇는다.

    **커서(워터마크)까지 구현이 소유한다**: pull_alertable()은 마지막으로 처리한
    news_labels.id 이후의 강한 감성 뉴스를 내주고 커서를 그 자리로 전진시킨다 —
    같은 뉴스가 두 번 나오지 않는 것이 계약이다(at-most-once: 호출 뒤 소비자가
    죽으면 그 배치는 유실된다 — 알림은 재발송보다 중복이 더 나쁘다는 판단).
    첫 호출(커서 부재)은 현재 최신 라벨을 커서로 삼고 빈 목록을 준다 —
    과거 라벨 백로그가 한꺼번에 알림으로 쏟아지는 것을 막는다.
    """

    @abstractmethod
    async def pull_alertable(
        self, min_abs_sentiment: float, limit: int = 200
    ) -> list[AlertableNews]:
        ...
