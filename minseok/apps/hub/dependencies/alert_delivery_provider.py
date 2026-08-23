from __future__ import annotations

from hub.app.ports.output.alert_delivery_port import AlertDeliveryPort


def get_alert_delivery_port() -> AlertDeliveryPort:
    """합성 루트(main.py)의 dependency_overrides로 스포크(recommendation) 구현을 주입한다."""
    raise NotImplementedError(
        "get_alert_delivery_port는 main.py의 dependency_overrides로 "
        "recommendation 구현을 주입해야 합니다."
    )
