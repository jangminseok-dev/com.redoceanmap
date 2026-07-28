from __future__ import annotations

from fastapi import Depends

from hub.app.ports.input.email_request_use_case import EmailRequestUseCase
from hub.app.ports.output.email_composer_port import EmailComposerPort
from hub.app.ports.output.member_directory_port import MemberDirectoryPort
from hub.app.use_cases.email_request_interactor import EmailRequestInteractor
from hub.dependencies.member_directory_provider import get_member_directory_port


def get_email_composer() -> EmailComposerPort:
    """합성 루트(main.py)의 dependency_overrides로 스포크 구현을 주입한다."""
    raise NotImplementedError(
        "get_email_composer는 main.py의 dependency_overrides로 스포크 구현을 주입해야 합니다."
    )


def get_email_request_use_case(
    composer: EmailComposerPort = Depends(get_email_composer),
    members: MemberDirectoryPort = Depends(get_member_directory_port),
) -> EmailRequestUseCase:
    return EmailRequestInteractor(composer=composer, members=members)
