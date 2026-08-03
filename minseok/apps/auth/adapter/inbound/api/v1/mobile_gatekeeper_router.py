from fastapi import APIRouter, Depends

from auth.adapter.inbound.api.schemas.mobile_gatekeeper_schema import (
    MobileGatekeeperResponseSchema,
)
from auth.app.dtos.mobile_gatekeeper_dto import MobileGatekeeperQuery
from auth.app.ports.input.mobile_gatekeeper_use_case import MobileGatekeeperUseCase
from auth.dependencies.mobile_gatekeeper_provider import get_mobile_gatekeeper_use_case

mobile_gatekeeper_router = APIRouter(prefix="/auth/mobile", tags=["auth"])


@mobile_gatekeeper_router.get("/myself", response_model=MobileGatekeeperResponseSchema)
async def introduce_myself(
    gatekeeper: MobileGatekeeperUseCase = Depends(get_mobile_gatekeeper_use_case),
) -> MobileGatekeeperResponseSchema:
    result = await gatekeeper.introduce_myself(
        MobileGatekeeperQuery(id=1, name="모바일 인증 (auth/mobile)")
    )
    return MobileGatekeeperResponseSchema(
        id=result.id, name=result.name, introduction=result.introduction
    )
