from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.adapter.outbound.gateways.kakao_identity_gateway import KakaoIdentityGateway
from auth.adapter.outbound.pg.grade_pg_repository import GradePgRepository
from auth.adapter.outbound.pg.user_pg_repository import UserPgRepository
from auth.adapter.outbound.redis.mobile_refresh_redis_repository import (
    MobileRefreshRedisRepository,
)
from auth.app.ports.input.mobile_auth_use_case import MobileAuthUseCase
from auth.app.use_cases.mobile_auth_interactor import MobileAuthInteractor
from core.database import get_db
from core.redis import get_redis_mobile


def get_mobile_auth_use_case(db: AsyncSession = Depends(get_db)) -> MobileAuthUseCase:
    return MobileAuthInteractor(
        identity_port=KakaoIdentityGateway(),
        repository=UserPgRepository(session=db),
        # 웹 세션(db 0)과 커넥션을 공유하지 않는다 — 모바일 전용 클라이언트다.
        refresh_repository=MobileRefreshRedisRepository(redis=get_redis_mobile()),
        grades=GradePgRepository(session=db),
    )
