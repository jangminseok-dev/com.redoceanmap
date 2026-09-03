from fastapi import Depends

from hub.app.ports.output.stock_signal_board_port import StockSignalBoardPort
from stock.adapter.outbound.gateways.stock_signal_board_gateway import StockSignalBoardGateway
from stock.app.ports.input.stock_board_use_case import StockBoardUseCase
from stock.dependencies.stock_board_provider import get_stock_board_use_case


def get_stock_signal_board_gateway(
    board: StockBoardUseCase = Depends(get_stock_board_use_case),
) -> StockSignalBoardPort:
    """허브 StockSignalBoardPort의 stock 구현. main.py가 주입한다."""
    return StockSignalBoardGateway(board=board)
