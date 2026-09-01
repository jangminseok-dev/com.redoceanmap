from __future__ import annotations

from hub.app.ports.output.price_alert_directory_port import PriceAlertDirectoryPort


def get_price_alert_directory_port() -> PriceAlertDirectoryPort:
    """합성 루트(main.py)의 dependency_overrides로 스포크(recommendation) 구현을 주입한다."""
    raise NotImplementedError(
        "get_price_alert_directory_port는 main.py의 dependency_overrides로 "
        "recommendation 구현을 주입해야 합니다."
    )
