from __future__ import annotations

from hub.app.ports.output.area_graph_port import AreaGraphPort


def get_area_graph_port() -> AreaGraphPort:
    """합성 루트(main.py)의 dependency_overrides로 스포크(market) 구현을 주입한다."""
    raise NotImplementedError(
        "get_area_graph_port는 main.py의 dependency_overrides로 market 구현을 주입해야 합니다."
    )
