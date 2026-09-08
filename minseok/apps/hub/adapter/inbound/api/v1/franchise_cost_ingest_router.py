"""franchise_cost_ingest_router.py — 공정위 업종별 창업비용 수집 배치(cron)의 적재 창구."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from hub.adapter.inbound.api.schemas.franchise_cost_schema import FranchiseCostIngestRequest, FranchiseCostIngestResult
from hub.adapter.inbound.api.v1.webhook_token import verify_webhook_token
from hub.app.dtos.franchise_cost_dto import FranchiseCostItem
from hub.app.ports.input.franchise_cost_ingest_use_case import FranchiseCostIngestUseCase
from hub.dependencies.franchise_cost_provider import get_franchise_cost_ingest_use_case

franchise_cost_ingest_router = APIRouter(
    prefix="/automation", tags=["automation"], dependencies=[Depends(verify_webhook_token)],
)


@franchise_cost_ingest_router.post("/franchise-costs", response_model=FranchiseCostIngestResult,
                                    summary="공정위 업종별 창업비용 적재 — (연도·부문·업종) 교체 멱등")
async def ingest_franchise_costs(
    payload: FranchiseCostIngestRequest,
    use_case: FranchiseCostIngestUseCase = Depends(get_franchise_cost_ingest_use_case),
) -> FranchiseCostIngestResult:
    saved = await use_case.ingest([
        FranchiseCostItem(year=i.year, sector=i.sector, industry_name=i.industryName, franchise_fee=i.franchiseFee,
                          education_fee=i.educationFee, deposit=i.deposit, other_fee=i.otherFee,
                          total_amount=i.totalAmount, brand_count=i.brandCount, raw=i.raw)
        for i in payload.items
    ])
    return FranchiseCostIngestResult(received=len(payload.items), saved=saved)
