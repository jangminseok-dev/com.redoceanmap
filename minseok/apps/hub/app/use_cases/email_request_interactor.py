from __future__ import annotations

from hub.app.dtos.email_request_dto import EmailRequestCommand, EmailRequestResult
from hub.app.ports.input.email_request_use_case import EmailRequestUseCase
from hub.app.ports.output.email_composer_port import EmailComposerPort
from hub.app.ports.output.member_directory_port import MemberDirectoryPort
from hub.domain.email.email_ontology import render_instruction


class EmailRequestInteractor(EmailRequestUseCase):
    """이메일 요청 허브 대장 — 온톨로지 지시를 합성해 작성·발송 포트(스포크)에 위임한다.

    수신자는 요청자 본인으로 고정한다(회원 디렉토리 조회). 임의 주소를 본문으로 받으면
    로그인만 하면 누구나 서비스 명의로 메일을 보내는 오픈 릴레이가 된다(2026-07-28).
    """

    def __init__(self, composer: EmailComposerPort, members: MemberDirectoryPort) -> None:
        self._composer = composer
        self._members = members

    async def request(self, command: EmailRequestCommand) -> EmailRequestResult:
        to_email = await self._members.find_email(command.requester_id)
        if to_email is None:
            raise ValueError("회원 이메일을 찾을 수 없습니다.")
        instruction = render_instruction(command.content)
        detail = await self._composer.compose_and_send(to_email, instruction)
        return EmailRequestResult(status="sent", detail=detail)
