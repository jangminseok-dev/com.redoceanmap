"""paper_router.py — AI 모의투자: 리더보드·계정·판단·채점 조회 + 사람 주문."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from core.security import get_current_user_id
from stock.adapter.inbound.api.schemas.paper_schema import (
    DecisionSchema, OrderReceiptSchema, PaperAccountResponse, PaperBoardResponse, PaperDecisionsResponse,
    PaperMyselfResponse, PaperScorecardResponse, PlaceOrderRequest, ScoreBucketSchema, ScoreSchema, TradeSchema,
)
from stock.app.dtos.paper_dto import AccountView, PlaceOrderCommand
from stock.app.exceptions import PaperOrderRejected
from stock.app.ports.input.paper_use_case import PaperUseCase
from stock.dependencies.paper_provider import get_paper_use_case
from stock.domain.services import paper_rules as rules

paper_router = APIRouter(prefix="/stock/paper", tags=["stock"])


def _account(view: AccountView) -> PaperAccountResponse:
    return PaperAccountResponse(
        key=view.key, kind=view.kind, label=view.label, cash_krw=view.cash_krw, equity_krw=view.equity_krw,
        initial_cash_krw=view.initial_cash_krw, started_on=view.started_on,
        positions=[asdict(p) for p in view.positions],
        equity=[asdict(e) for e in view.equity],
        trades=[TradeSchema(**{k: v for k, v in asdict(t).items() if k != "account_id"}) for t in view.trades],
    )


@paper_router.get("/myself", response_model=PaperMyselfResponse)
async def introduce_myself() -> PaperMyselfResponse:
    return PaperMyselfResponse(
        name="AI 모의투자",
        description=(
            "실제 매매가 아닌 기록입니다. EXAONE 계정은 매일 14:00 동결된 예측 스냅샷·뉴스 라벨을 읽고 "
            "종목·방향·비중을 판단하며, 그 판단은 다음 세션 시가에 사후 체결됩니다. 지표 규칙 계정은 "
            "검증된 지표 조합을 그대로 따르는 대조군이고, 사람은 같은 규칙(초기 자본·수수료·한도)으로 "
            "지연 시세에 즉시 체결해 참가합니다. 매매 권유가 아니며 '어느 계정이 무엇을 샀다'는 사실만 "
            "보고합니다. 체결 축이 다르므로(AI 다음 세션 시가 · 사람 최신 저장 봉 종가) 성적을 같은 "
            "조건의 대결로 읽지 마세요."
        ),
        endpoints=[
            "GET /stock/paper/myself — 이 소개",
            "GET /stock/paper/board — 리더보드 + SPY 기준선",
            "GET /stock/paper/accounts/{key} — 계정(곡선·포지션·거래)",
            "GET /stock/paper/accounts/{key}/decisions — 일별 판단(후보·주문·거부·체결·채점)",
            "GET /stock/paper/accounts/{key}/scorecard — 판단 사후 채점",
            "GET /stock/paper/me · POST /stock/paper/me/orders — 내 계정·주문(로그인)",
        ],
        rules={
            "assumed_initial_cash_krw": rules.assumed_initial_cash_krw,
            "assumed_fee_rate": rules.assumed_fee_rate,
            "assumed_usdkrw": rules.assumed_usdkrw,
            "assumed_max_position_weight": rules.assumed_max_position_weight,
            "assumed_max_positions": rules.assumed_max_positions,
        },
    )


@paper_router.get("/board", response_model=PaperBoardResponse)
async def board(use_case: PaperUseCase = Depends(get_paper_use_case)) -> PaperBoardResponse:
    view = await use_case.board()
    return PaperBoardResponse(rows=[asdict(r) for r in view.rows], spy=[asdict(p) for p in view.spy],
                              replay_until=view.replay_until, rules=view.rules)


@paper_router.get("/me", response_model=PaperAccountResponse)
async def my_account(
    user_id: int = Depends(get_current_user_id), use_case: PaperUseCase = Depends(get_paper_use_case),
) -> PaperAccountResponse:
    return _account(await use_case.me(user_id))


@paper_router.post("/me/orders", response_model=OrderReceiptSchema)
async def place_order(
    payload: PlaceOrderRequest,
    user_id: int = Depends(get_current_user_id), use_case: PaperUseCase = Depends(get_paper_use_case),
) -> OrderReceiptSchema:
    try:
        receipt = await use_case.place_order(PlaceOrderCommand(user_id, payload.ticker, payload.action, payload.quantity))
    except PaperOrderRejected as e:
        raise HTTPException(status_code=409, detail=e.detail) from e
    return OrderReceiptSchema(**asdict(receipt))


@paper_router.get("/accounts/{key}", response_model=PaperAccountResponse)
async def account(key: str, use_case: PaperUseCase = Depends(get_paper_use_case)) -> PaperAccountResponse:
    view = await use_case.account(key)
    if view is None:
        raise HTTPException(status_code=404, detail=f"계정을 찾지 못했습니다: {key}")
    return _account(view)


@paper_router.get("/accounts/{key}/decisions", response_model=PaperDecisionsResponse)
async def decisions(
    key: str,
    since: date | None = Query(default=None), until: date | None = Query(default=None),
    limit: int = Query(default=60, ge=1, le=400),
    use_case: PaperUseCase = Depends(get_paper_use_case),
) -> PaperDecisionsResponse:
    views = await use_case.decisions(key, since, until, limit)
    return PaperDecisionsResponse(key=key, decisions=[
        DecisionSchema(
            id=d.id, as_of=d.as_of, market_view=d.market_view, orders=d.orders, rejected=d.rejected,
            candidates=d.candidates,
            fills=[TradeSchema(**{k: v for k, v in asdict(t).items() if k != "account_id"}) for t in d.fills],
            scores=[ScoreSchema(ticker=s.ticker, action=s.action, reason_kind=s.reason_kind,
                                realized_return_pct=s.realized_return_pct, hit=s.hit) for s in d.scores],
            replayed=d.replayed, latency_ms=d.latency_ms,
        ) for d in views
    ])


@paper_router.get("/accounts/{key}/scorecard", response_model=PaperScorecardResponse)
async def scorecard(key: str, use_case: PaperUseCase = Depends(get_paper_use_case)) -> PaperScorecardResponse:
    view = await use_case.scorecard(key)
    if view is None:
        raise HTTPException(status_code=404, detail=f"계정을 찾지 못했습니다: {key}")
    return PaperScorecardResponse(
        key=key, total=ScoreBucketSchema(**asdict(view.total)),
        by_reason=[ScoreBucketSchema(**asdict(b)) for b in view.by_reason],
        by_action=[ScoreBucketSchema(**asdict(b)) for b in view.by_action], min_samples=view.min_samples,
    )
