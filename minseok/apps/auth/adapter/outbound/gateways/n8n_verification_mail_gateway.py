from __future__ import annotations

import logging

import httpx

from auth.app.ports.output.verification_mail_port import VerificationMailPort
from core.config import N8N_EMAIL_WEBHOOK_URL, N8N_OUTBOUND_TOKEN

logger = logging.getLogger(__name__)

_SUBJECT = "[redoceanmap] 이메일 주소를 확인해 주세요"
_BODY = (
    "redoceanmap 알림 메일을 받으려면 아래 링크를 눌러 이메일 주소를 확인해 주세요.\n\n"
    "{link}\n\n"
    "링크는 24시간 동안 한 번만 쓸 수 있어요.\n"
    "본인이 요청하지 않았다면 이 메일을 무시하셔도 됩니다 — 아무 일도 일어나지 않아요."
)


class N8nVerificationMailGateway(VerificationMailPort):
    """인증 메일을 n8n 웹훅(redocean-email → Gmail)으로 보낸다. 문구는 고정 — LLM을 거치지 않는다."""

    async def send(self, to_email: str, link: str) -> None:
        payload = {"to": to_email, "subject": _SUBJECT, "body": _BODY.format(link=link)}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(N8N_EMAIL_WEBHOOK_URL, json=payload, headers={"X-Webhook-Token": N8N_OUTBOUND_TOKEN})
            response.raise_for_status()
        logger.info("[auth-email] 인증 메일 발송 → %s", to_email.split("@")[-1])  # 주소 전체는 로그에 남기지 않는다
