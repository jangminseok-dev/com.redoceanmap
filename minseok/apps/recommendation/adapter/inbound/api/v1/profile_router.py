"""profile_router.py — 투자·창업 프로파일 설문(저장·조회·삭제, 밴드 기반)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core.security import get_current_user_id
from recommendation.adapter.inbound.api.schemas.profile_schema import (
    ProfileDeleteResponse,
    ProfileEnvelope,
    ProfileMyselfResponse,
    ProfileResponse,
    ProfileSaveRequest,
)
from recommendation.app.dtos.profile_dto import ProfileDraft
from recommendation.app.ports.input.profile_use_case import ProfileUseCase
from recommendation.dependencies.profile_provider import get_profile_use_case
from recommendation.domain.entities.profile_entity import InvestorProfile

profile_router = APIRouter(prefix="/profile", tags=["recommendations"])


def _to_schema(p: InvestorProfile) -> ProfileResponse:
    return ProfileResponse(
        purpose=p.purpose, risk_level=p.risk_level, budget_band=p.budget_band,
        debt_burden=p.debt_burden, horizon=p.horizon, updated_at=p.updated_at,
    )


@profile_router.get("/myself", response_model=ProfileMyselfResponse)
async def introduce_myself() -> ProfileMyselfResponse:
    return ProfileMyselfResponse(
        name="투자·창업 프로파일",
        description=(
            "자기신고 설문(목적·투자성향·예산 밴드·부채 부담·투자 기간)을 저장하는 창구입니다. "
            "정확한 금액·계좌·신용점수는 받지 않고 구간(밴드)만 저장하며, 이 프로파일은 "
            "상권·주식 분석 서술의 관점 조정에만 쓰입니다 — 매매 지시나 상품 추천의 근거가 "
            "되지 않습니다. 사용자당 1건, 재작성은 덮어쓰기입니다."
        ),
        endpoints=[
            "GET /profile/myself — 이 소개",
            "GET /profile — 내 프로파일(미작성이면 profile=null)",
            "PUT /profile — 저장/재작성 {purpose, risk_level, budget_band, debt_burden, horizon}",
            "DELETE /profile — 삭제",
        ],
    )


@profile_router.get("", response_model=ProfileEnvelope)
async def get_my_profile(
    user_id: int = Depends(get_current_user_id),
    use_case: ProfileUseCase = Depends(get_profile_use_case),
) -> ProfileEnvelope:
    profile = await use_case.get_mine(user_id)
    return ProfileEnvelope(profile=_to_schema(profile) if profile else None)


@profile_router.put("", response_model=ProfileResponse)
async def save_my_profile(
    payload: ProfileSaveRequest,
    user_id: int = Depends(get_current_user_id),
    use_case: ProfileUseCase = Depends(get_profile_use_case),
) -> ProfileResponse:
    try:
        saved = await use_case.save(ProfileDraft(
            user_id=user_id, purpose=payload.purpose, risk_level=payload.risk_level,
            budget_band=payload.budget_band, debt_burden=payload.debt_burden,
            horizon=payload.horizon,
        ))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _to_schema(saved)


@profile_router.delete("", response_model=ProfileDeleteResponse)
async def delete_my_profile(
    user_id: int = Depends(get_current_user_id),
    use_case: ProfileUseCase = Depends(get_profile_use_case),
) -> ProfileDeleteResponse:
    # 없는 것을 지워도 200(deleted=false) — 북마크와 같은 멱등 규칙
    return ProfileDeleteResponse(deleted=await use_case.remove(user_id))
