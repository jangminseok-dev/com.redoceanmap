from datetime import UTC, datetime

import pytest

from stock.app.dtos.stock_board_dto import BoardQuery, BoardSignalRow
from stock.app.ports.output.stock_board_repository import StockBoardRepositoryPort
from stock.app.ports.output.symbol_directory_port import SymbolDirectoryPort
from stock.app.use_cases.stock_board_interactor import StockBoardInteractor

AS_OF = datetime(2026, 7, 22, tzinfo=UTC)


def _row(ticker: str, direction: str, score: float, **kwargs) -> BoardSignalRow:
    defaults = dict(
        as_of=AS_OF,
        base_price=100.0,
        up_rate=None,
        baseline_up_rate=None,
        ready=False,
        closes=(98.0, 100.0),
        price_as_of=AS_OF,
    )
    defaults.update(kwargs)
    return BoardSignalRow(ticker=ticker, direction=direction, score=score, **defaults)


class _StubRepository(StockBoardRepositoryPort):
    def __init__(self, rows: list[BoardSignalRow]) -> None:
        self.rows = rows
        self.calls: list[tuple[int, int]] = []

    async def find_latest_signals(self, horizon: int, sparkline_bars: int):
        self.calls.append((horizon, sparkline_bars))
        return self.rows


class _StubDirectory(SymbolDirectoryPort):
    def display_name(self, ticker: str) -> str:
        return {"NVDA": "엔비디아"}.get(ticker, ticker)


def _interactor(rows: list[BoardSignalRow]) -> tuple[StockBoardInteractor, _StubRepository]:
    repo = _StubRepository(rows)
    return StockBoardInteractor(repository=repo, directory=_StubDirectory()), repo


async def test_신호가_뚜렷한_순서로_줄세운다():
    interactor, _ = _interactor([
        _row("AAA", "UP", 0.10),
        _row("BBB", "DOWN", -0.55),
        _row("CCC", "UP", 0.40),
    ])
    view = await interactor.board(BoardQuery(horizon=5, limit=10))
    assert [r.ticker for r in view.rows] == ["BBB", "CCC", "AAA"]  # |score| 내림차순


async def test_중립은_점수가_높아도_뒤로_민다():
    interactor, _ = _interactor([
        _row("NEU", "NEUTRAL", 0.90),
        _row("UPP", "UP", 0.10),
    ])
    view = await interactor.board(BoardQuery(horizon=5, limit=10))
    assert [r.ticker for r in view.rows] == ["UPP", "NEU"]


async def test_limit_만큼만_돌려준다():
    interactor, _ = _interactor([_row(f"T{i}", "UP", 0.5 - i * 0.01) for i in range(10)])
    view = await interactor.board(BoardQuery(horizon=5, limit=3))
    assert len(view.rows) == 3
    assert view.horizon_days == 5


async def test_이름과_전일_대비를_채운다():
    interactor, _ = _interactor([_row("NVDA", "UP", 0.5, closes=(200.0, 210.0))])
    row = (await interactor.board(BoardQuery(horizon=5, limit=10))).rows[0]
    assert row.name == "엔비디아"
    assert row.price == 210.0  # 스냅샷 base_price가 아니라 마지막 봉
    assert row.change_pct == pytest.approx(0.05)


async def test_봉이_한_개면_전일_대비는_None이다():
    interactor, _ = _interactor([_row("AAA", "UP", 0.5, closes=(210.0,))])
    row = (await interactor.board(BoardQuery(horizon=5, limit=10))).rows[0]
    assert row.change_pct is None
    assert row.price == 210.0


async def test_봉이_없으면_base_price로_열화한다():
    interactor, _ = _interactor([_row("AAA", "UP", 0.5, base_price=123.0, closes=())])
    row = (await interactor.board(BoardQuery(horizon=5, limit=10))).rows[0]
    assert row.price == 123.0
    assert row.change_pct is None


async def test_확률과_기준선이_모두_있을_때만_edge를_낸다():
    interactor, _ = _interactor([
        _row("AAA", "UP", 0.5, up_rate=0.58, baseline_up_rate=0.55),
        _row("BBB", "DOWN", -0.6, up_rate=0.40, baseline_up_rate=None),
    ])
    rows = {r.ticker: r for r in (await interactor.board(BoardQuery(horizon=5, limit=10))).rows}
    assert rows["AAA"].edge_pct == pytest.approx(0.03)
    assert rows["BBB"].edge_pct is None


async def test_가격_기준일을_그대로_전달한다():
    # 신호 기준일(as_of)보다 가격이 최신일 수 있어 화면이 둘을 구분해 적어야 한다
    later = datetime(2026, 7, 23, tzinfo=UTC)
    interactor, _ = _interactor([_row("AAA", "UP", 0.5, price_as_of=later)])
    row = (await interactor.board(BoardQuery(horizon=5, limit=10))).rows[0]
    assert row.as_of == AS_OF
    assert row.price_as_of == later


async def test_horizon을_리포지토리에_그대로_넘긴다():
    interactor, repo = _interactor([])
    await interactor.board(BoardQuery(horizon=20, limit=5))
    assert repo.calls == [(20, 300)]  # RISK_BARS — 스파크라인은 그중 최근 30봉


# --- 위험 신호 순(2026-09-17 재설계) ---

def _closes(n: int, calm_until: int, step: float = 0.004) -> tuple[float, ...]:
    """앞은 잔잔하다가 calm_until부터 크게 흔들리는 종가 — 최신 변동성이 자기 분포 상위로 간다."""
    import math
    out, price = [], 100.0
    for i in range(n):
        amp = 0.05 if i >= calm_until else step
        price *= math.exp(amp if i % 2 else -amp * 0.9)
        out.append(price)
    return tuple(out)


class _ReportRepository(_StubRepository):
    async def find_latest_risk_report(self):
        payload = {"train_end_year": 2020, "last_date": "2026-09-16", "signals": [{
            "key": "vol_high", "label": "변동성 확대 가능성 높음", "outcome_label": "20거래일 안에 변동성이 커짐",
            "side": "high", "validated": True,
            "train": {"lift": 1.77}, "test": {"rate": 0.513, "base": 0.326, "lift": 1.57, "n_eff": 1274.0},
        }]}
        return AS_OF, payload


async def test_위험_순_정렬은_변동성이_튄_종목을_위로_올리고_검증_실측을_싣는다():
    calm = _row("CALM", "UP", 0.9, closes=_closes(300, calm_until=300))
    wild = _row("WILD", "NEUTRAL", 0.0, closes=_closes(300, calm_until=285))
    repo = _ReportRepository([calm, wild])
    view = await StockBoardInteractor(repository=repo, directory=_StubDirectory()).board(
        BoardQuery(horizon=5, limit=10, order="risk"))
    assert [r.ticker for r in view.rows] == ["WILD", "CALM"]
    assert view.rows[0].vol_state == "HIGH" and len(view.rows[0].sparkline) == 30
    stat = view.risk_stats[0]
    assert stat.validated and stat.test_rate == 0.513 and stat.lift == 1.57
    assert view.risk_test_period == "2021-01~2026-09"


async def test_봉이_모자라면_위험_신호는_비운다():
    interactor, _ = _interactor([_row("NEW", "UP", 0.3)])
    view = await interactor.board(BoardQuery(horizon=5, limit=10, order="risk"))
    assert view.rows[0].vol_state is None and view.risk_stats == ()
