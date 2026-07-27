from __future__ import annotations

from hub.app.ports.output.news_event_study_port import NewsEventStudyPort


def get_news_event_study_port() -> NewsEventStudyPort:
    """합성 루트(main.py)의 dependency_overrides로 스포크(stock) 구현을 주입한다."""
    raise NotImplementedError(
        "get_news_event_study_port는 main.py의 dependency_overrides로 stock 구현을 주입해야 합니다."
    )
