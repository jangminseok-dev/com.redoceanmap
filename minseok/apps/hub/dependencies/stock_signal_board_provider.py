from __future__ import annotations

from hub.app.ports.output.stock_signal_board_port import StockSignalBoardPort


def get_stock_signal_board_port() -> StockSignalBoardPort:
    """합성 루트(main.py)의 dependency_overrides로 스포크(stock) 구현을 주입한다."""
    raise NotImplementedError(
        "get_stock_signal_board_port는 main.py의 dependency_overrides로 stock 구현을 주입해야 합니다."
    )
