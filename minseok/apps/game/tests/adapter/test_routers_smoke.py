"""라우터 스모크 — DTO → 스키마 변환이 실제로 통과하는지.

라우터가 필드를 손으로 옮겨 담기 때문에(camelCase 변환) 오타가 나면 런타임에만 터진다.
DB·인증은 의존성 오버라이드로 걷어내고 **변환 경로만** 확인한다.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security import get_current_user_id
from game.adapter.inbound.api.v1.market_price_router import market_price_router
from game.adapter.inbound.api.v1.rulebook_router import rulebook_router
from game.adapter.inbound.api.v1.trade_router import trade_router
from game.adapter.inbound.api.v1.wallet_router import wallet_router
from game.app.use_cases.market_price_interactor import MarketPriceInteractor
from game.app.use_cases.rulebook_interactor import RulebookInteractor
from game.app.use_cases.trade_interactor import TradeInteractor
from game.app.use_cases.wallet_interactor import WalletInteractor
from game.dependencies.market_price_provider import get_market_price_use_case
from game.dependencies.rulebook_provider import get_rulebook_use_case
from game.dependencies.trade_provider import get_trade_use_case
from game.dependencies.wallet_provider import get_wallet_use_case
from game.domain.market.symbol_params import SYMBOLS
from game.tests.app.use_cases.stub_account_repository import StubAccountRepository, StubClock

USER = 42
TICK = 1_500


class _StubRecord:
    async def record(self, subject: str, note: str) -> None:  # noqa: D102
        pass


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    for router in (rulebook_router, market_price_router, wallet_router, trade_router):
        app.include_router(router)

    repository = StubAccountRepository()
    clock = StubClock(TICK)

    app.dependency_overrides[get_current_user_id] = lambda: USER
    app.dependency_overrides[get_rulebook_use_case] = lambda: RulebookInteractor(
        record=_StubRecord(), clock=clock
    )
    app.dependency_overrides[get_market_price_use_case] = lambda: MarketPriceInteractor(clock=clock)
    app.dependency_overrides[get_wallet_use_case] = lambda: WalletInteractor(
        repository=repository, clock=clock
    )
    app.dependency_overrides[get_trade_use_case] = lambda: TradeInteractor(
        repository=repository, clock=clock
    )
    return TestClient(app)


def test_myself는_실기능과_게임_시각을_낸다(client):
    body = client.get("/game/myself").json()
    assert body["tick"] == TICK
    assert body["gameQuarter"] >= 1
    assert "가상" in body["introduction"]


def test_시세는_가상임을_밝힌다(client):
    body = client.get("/game/market/prices?ticks=10").json()
    assert body["virtual"] is True
    assert len(body["symbols"]) == len(SYMBOLS)
    assert len(body["symbols"][0]["series"]) == 10


def test_ticks_범위_밖은_422다(client):
    assert client.get("/game/market/prices?ticks=9999").status_code == 422


def test_지갑은_초기자본으로_자동_생성된다(client):
    body = client.get("/game/wallet").json()
    assert body["cashKrw"] == 1_000_000
    assert body["investableKrw"] == 900_000
    assert body["positions"] == []


def test_매매_왕복이_지갑에_반영된다(client):
    symbol = SYMBOLS[0].symbol
    opened = client.post(
        "/game/trades", json={"symbol": symbol, "side": "LONG", "quantity": 2}
    )
    assert opened.status_code == 200
    receipt = opened.json()
    assert receipt["cashDeltaKrw"] < 0
    assert receipt["realizedPnlKrw"] is None

    wallet = client.get("/game/wallet").json()
    assert len(wallet["positions"]) == 1
    assert wallet["positions"][0]["symbol"] == symbol

    closed = client.post(f"/game/trades/{receipt['positionId']}/close")
    assert closed.status_code == 200
    assert closed.json()["realizedPnlKrw"] is not None
    assert client.get("/game/wallet").json()["positions"] == []


def test_없는_종목은_404_잘못된_수량은_422다(client):
    assert (
        client.post("/game/trades", json={"symbol": "NOPE", "side": "LONG", "quantity": 1}).status_code
        == 404
    )
    # quantity gt=0은 pydantic이 먼저 막는다
    assert (
        client.post("/game/trades", json={"symbol": "GX01", "side": "LONG", "quantity": 0}).status_code
        == 422
    )


def test_예산을_넘는_주문은_400이다(client):
    body = client.post(
        "/game/trades", json={"symbol": "GX01", "side": "LONG", "quantity": 999_999}
    )
    assert body.status_code == 400


def test_없는_포지션_청산은_404다(client):
    assert client.post("/game/trades/999/close").status_code == 404
