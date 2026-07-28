import pytest

from hub.app.dtos.email_request_dto import EmailRequestCommand
from hub.app.use_cases.email_request_interactor import EmailRequestInteractor
from hub.domain.email.email_ontology import OUTBOUND_EMAIL_DIRECTIVE, render_instruction


class _StubComposer:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    async def compose_and_send(self, to_email, instruction):
        self.calls.append((to_email, instruction))
        return "n8n 200"


class _StubMembers:
    """MemberDirectoryPort 중 이 유스케이스가 쓰는 find_email만 흉내낸다."""

    def __init__(self, emails: dict[int, str]):
        self.emails = emails

    async def find_email(self, user_id):
        return self.emails.get(user_id)


def test_온톨로지_지시는_규범을_담는다():
    instruction = render_instruction("7월 상권 리포트 안내")
    assert OUTBOUND_EMAIL_DIRECTIVE.tone in instruction
    assert "인사말 → 핵심 본문 → 맺음말" in instruction
    assert "7월 상권 리포트 안내" in instruction


async def test_요청은_온톨로지_지시를_합성해_포트에_위임():
    composer = _StubComposer()
    members = _StubMembers({7: "user@test.com"})
    result = await EmailRequestInteractor(composer, members).request(
        EmailRequestCommand(requester_id=7, content="테스트 내용")
    )
    assert result.status == "sent" and result.detail == "n8n 200"
    to, instruction = composer.calls[0]
    assert to == "user@test.com"
    assert instruction == render_instruction("테스트 내용")


async def test_수신자는_요청자_본인_이메일로_고정된다():
    """오픈 릴레이 회귀 방지 — 수신자는 요청 본문이 아니라 회원 디렉토리에서만 온다."""
    composer = _StubComposer()
    members = _StubMembers({7: "owner@test.com", 8: "other@test.com"})
    await EmailRequestInteractor(composer, members).request(
        EmailRequestCommand(requester_id=8, content="피싱 시도")
    )
    assert composer.calls[0][0] == "other@test.com"
    assert not hasattr(EmailRequestCommand(requester_id=8, content="x"), "to_email")


async def test_회원_이메일이_없으면_발송하지_않는다():
    composer = _StubComposer()
    with pytest.raises(ValueError):
        await EmailRequestInteractor(composer, _StubMembers({})).request(
            EmailRequestCommand(requester_id=99, content="테스트")
        )
    assert composer.calls == []
