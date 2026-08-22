from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from hub.app.ports.output.user_profile_port import UserProfilePort
from recommendation.adapter.outbound.gateways.user_profile_gateway import UserProfileGateway
from recommendation.adapter.outbound.pg.profile_pg_repository import ProfilePgRepository
from recommendation.app.ports.input.profile_use_case import ProfileUseCase
from recommendation.app.use_cases.profile_interactor import ProfileInteractor


def get_profile_use_case(db: AsyncSession = Depends(get_db)) -> ProfileUseCase:
    return ProfileInteractor(profiles=ProfilePgRepository(session=db))


def get_user_profile_gateway(
    use_case: ProfileUseCase = Depends(get_profile_use_case),
) -> UserProfilePort:
    """허브 UserProfilePort의 recommendation 구현. main.py가 주입한다."""
    return UserProfileGateway(use_case=use_case)
