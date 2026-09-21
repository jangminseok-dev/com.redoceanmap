from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth.adapter.outbound.gateways.n8n_verification_mail_gateway import N8nVerificationMailGateway
from auth.adapter.outbound.pg.user_pg_repository import UserPgRepository
from auth.adapter.outbound.redis.email_verification_token_redis_repository import EmailVerificationTokenRedisRepository
from auth.app.ports.input.email_verification_use_case import EmailVerificationUseCase
from auth.app.use_cases.email_verification_interactor import EmailVerificationInteractor
from core.config import SITE_URL
from core.database import get_db
from core.redis import get_redis


def get_email_verification_use_case(db: AsyncSession = Depends(get_db)) -> EmailVerificationUseCase:
    return EmailVerificationInteractor(
        users=UserPgRepository(session=db),
        tokens=EmailVerificationTokenRedisRepository(redis=get_redis()),
        mail=N8nVerificationMailGateway(),
        site_url=SITE_URL,
    )
