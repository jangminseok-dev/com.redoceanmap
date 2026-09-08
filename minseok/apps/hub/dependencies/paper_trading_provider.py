from __future__ import annotations

from hub.app.ports.output.paper_decision_port import PaperDecisionPort
from hub.app.ports.output.paper_trading_port import PaperTradingPort


def get_paper_trading_port() -> PaperTradingPort:
    """합성 루트(main.py)의 dependency_overrides로 스포크(stock) 구현을 주입한다."""
    raise NotImplementedError("get_paper_trading_port는 main.py의 dependency_overrides로 stock 구현을 주입해야 합니다.")


def get_paper_decision_port() -> PaperDecisionPort:
    raise NotImplementedError("get_paper_decision_port는 main.py의 dependency_overrides로 stock 구현을 주입해야 합니다.")
