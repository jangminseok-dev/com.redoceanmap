from __future__ import annotations

import logging

from auth.app.dtos.email_verification_dto import VerifyRequestOutcome
from auth.app.ports.input.email_verification_use_case import EmailVerificationUseCase
from auth.app.ports.output.email_verification_token_repository import EmailVerificationTokenRepository
from auth.app.ports.output.user_repository import UserRepository
from auth.app.ports.output.verification_mail_port import VerificationMailPort
from auth.domain.value_objects import email_verification as policy
from auth.domain.value_objects.deliverable_email import is_deliverable

logger = logging.getLogger(__name__)


class EmailVerificationInteractor(EmailVerificationUseCase):
    def __init__(
        self,
        users: UserRepository,
        tokens: EmailVerificationTokenRepository,
        mail: VerificationMailPort,
        site_url: str,
    ) -> None:
        self._users = users
        self._tokens = tokens
        self._mail = mail
        self._site_url = site_url

    async def request(self, user_id: int) -> VerifyRequestOutcome:
        user = await self._users.find_by_id(user_id)
        if user is None or not user.email:
            return VerifyRequestOutcome.NO_EMAIL
        if user.email_verified_at is not None:
            return VerifyRequestOutcome.ALREADY_VERIFIED
        if not is_deliverable(user.email):
            return VerifyRequestOutcome.UNDELIVERABLE
        # 제한을 먼저 잡는다 — 발송이 실패해도 n8n·Gmail을 연타하지 않게
        if not await self._tokens.try_acquire_request(user.id, policy.REQUEST_COOLDOWN, policy.DAILY_REQUEST_LIMIT):
            return VerifyRequestOutcome.THROTTLED
        token = policy.new_token()
        await self._tokens.save(policy.token_hash(token), user.id, user.email, policy.TOKEN_TTL)
        await self._mail.send(user.email, policy.verify_link(self._site_url, token))
        return VerifyRequestOutcome.SENT

    async def confirm(self, token: str) -> bool:
        if not token:
            return False
        found = await self._tokens.consume(policy.token_hash(token))
        if found is None:
            return False
        user_id, issued_email = found
        user = await self._users.find_by_id(user_id)
        # 토큰은 발급 당시의 주소를 증명한다 — 그 사이 주소가 달라졌거나 탈퇴·정지됐으면 인정하지 않는다
        if user is None or user.email != issued_email or user.deleted_at is not None or user.suspended_at is not None:
            return False
        await self._users.mark_email_verified(user.id)
        logger.info("[auth-email] 인증 완료 user=%d", user.id)
        return True
