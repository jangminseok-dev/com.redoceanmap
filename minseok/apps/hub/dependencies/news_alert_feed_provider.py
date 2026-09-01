from __future__ import annotations

from hub.app.ports.output.news_alert_feed_port import NewsAlertFeedPort


def get_news_alert_feed_port() -> NewsAlertFeedPort:
    """합성 루트(main.py)의 dependency_overrides로 스포크(stock) 구현을 주입한다."""
    raise NotImplementedError(
        "get_news_alert_feed_port는 main.py의 dependency_overrides로 "
        "stock 구현을 주입해야 합니다."
    )
