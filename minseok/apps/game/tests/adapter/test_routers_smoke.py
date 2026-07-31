"""라우터 스모크 — DTO → 스키마 변환이 실제로 통과하는지.

라우터가 필드를 손으로 옮겨 담기 때문에(camelCase 변환) 오타가 나면 런타임에만 터진다.
DB·인증은 의존성 오버라이드로 걷어내고 **변환 경로만** 확인한다.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security import get_current_user_id
from game.adapter.inbound.api.v1.area_fitness_router import area_fitness_router
from game.adapter.inbound.api.v1.market_price_router import market_price_router
from game.adapter.inbound.api.v1.rulebook_router import rulebook_router
from game.adapter.inbound.api.v1.settlement_router import settlement_router
from game.adapter.inbound.api.v1.store_daily_router import store_daily_router
from game.adapter.inbound.api.v1.store_open_router import store_open_router
from game.adapter.inbound.api.v1.trade_router import trade_router
from game.adapter.inbound.api.v1.wallet_router import wallet_router
from game.app.use_cases.area_fitness_interactor import AreaFitnessInteractor
from game.app.use_cases.market_price_interactor import MarketPriceInteractor
from game.app.use_cases.rulebook_interactor import RulebookInteractor
from game.app.use_cases.settlement_interactor import SettlementInteractor
from game.app.use_cases.store_daily_interactor import StoreDailyInteractor
from game.app.use_cases.store_open_interactor import StoreOpenInteractor
from game.app.use_cases.trade_interactor import TradeInteractor
from game.app.use_cases.wallet_interactor import WalletInteractor
from game.dependencies.area_fitness_provider import get_area_fitness_use_case
from game.dependencies.market_price_provider import get_market_price_use_case
from game.dependencies.rulebook_provider import get_rulebook_use_case
from game.dependencies.settlement_provider import get_settlement_use_case
from game.dependencies.store_daily_provider import get_store_daily_use_case
from game.dependencies.store_open_provider import get_store_open_use_case
from game.dependencies.trade_provider import get_trade_use_case
from game.dependencies.wallet_provider import get_wallet_use_case
from game.domain.market.symbol_params import SYMBOLS
from game.tests.app.use_cases.stub_account_repository import StubAccountRepository, StubClock
from game.tests.app.use_cases.stub_store_repository import StubStoreRepository
from game.tests.app.use_cases.test_area_fitness_interactor import _StubProfiles, _profile

USER = 42
TICK = 1_500


class _StubRecord:
    async def record(self, subject: str, note: str) -> None:  # noqa: D102
        pass


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    for router in (
        rulebook_router,
        market_price_router,
        wallet_router,
        trade_router,
        area_fitness_router,
        store_open_router,
        store_daily_router,
        settlement_router,
    ):
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
    app.dependency_overrides[get_area_fitness_use_case] = lambda: AreaFitnessInteractor(
        profiles=_StubProfiles(_profile())
    )
    stores = StubStoreRepository(accounts=repository)
    app.dependency_overrides[get_store_open_use_case] = lambda: StoreOpenInteractor(
        profiles=_StubProfiles(_profile()), stores=stores, accounts=repository, clock=clock
    )
    app.dependency_overrides[get_store_daily_use_case] = lambda: StoreDailyInteractor(
        stores=stores, clock=clock
    )
    app.dependency_overrides[get_settlement_use_case] = lambda: SettlementInteractor(
        stores=stores, clock=clock
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


def test_입지_적합도_미리보기가_실데이터와_게임값을_구분해_낸다(client):
    body = client.get("/game/areas/1001/fitness?service_code=CS100010").json()

    # 접두사가 곧 출처다 — observed는 실데이터, simulated는 게임 규칙
    assert body["observedSalesPerStore"] > 0
    assert body["simulatedMonthlySalesKrw"] > 0
    assert 0.4 <= body["fitness"] <= 1.6
    assert len(body["components"]) == 4
    assert body["diagnoses"]


def test_업종_코드가_없으면_422다(client):
    assert client.get("/game/areas/1001/fitness").status_code == 422


def test_창업하고_현황을_조회한다(client):
    opened = client.post(
        "/game/stores",
        json={
            "trdarCode": 1001,
            "serviceCode": "CS100010",
            "budgetKrw": 500_000,
            "staffCount": 2,
            "priceFactor": 1.0,
        },
    )
    assert opened.status_code == 200
    receipt = opened.json()
    assert receipt["cashDeltaKrw"] < 0
    assert 0.02 <= receipt["storeScale"] <= 1.0

    listed = client.get("/game/stores").json()
    assert len(listed) == 1

    # 시설 점수는 입력이 아니라 자본·수요에서 역산된다 — 영수증이 정본이다
    assert receipt["facilityScore"] >= 10
    assert receipt["seatCount"] == receipt["facilityScore"] // 10
    assert receipt["takeoutRatio"] > 0  # 커피-음료는 포장 비중이 높다

    detail = client.get(f"/game/stores/{receipt['storeId']}?days=7").json()
    assert detail["seats"] == receipt["seatCount"]
    assert detail["rows"]
    assert detail["customersByAge"]


def test_없는_가게_조회는_404다(client):
    assert client.get("/game/stores/999").status_code == 404


def test_창업_조건이_범위를_벗어나면_422다(client):
    body = client.post(
        "/game/stores",
        json={"trdarCode": 1001, "serviceCode": "CS100010", "budgetKrw": 500_000,
              "staffCount": 99999, "priceFactor": 1.0},
    )
    assert body.status_code == 422


def test_결산은_조회_시점에_밀린_분기를_확정한다(client):
    """cron이 없으므로 조회가 곧 정산 시점이다(지연 실행)."""
    body = client.get("/game/settlements").json()
    assert body["settlements"] == []  # 틱 1,500 = 게임 25일 — 아직 분기가 안 끝났다
    assert body["newlySettled"] == 0
    assert body["gameQuarter"] >= 1
