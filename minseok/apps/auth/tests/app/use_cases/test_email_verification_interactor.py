"""이메일 인증 유스케이스 — 스텁 포트로 검증. 인증은 알림 메일 수신 조건이지 가입·로그인의 관문이 아니다."""
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from auth.app.dtos.email_verification_dto import VerifyRequestOutcome
from auth.app.use_cases.email_verification_interactor import EmailVerificationInteractor
from auth.domain.entities.user_entity import User
from auth.domain.value_objects import email_verification as policy

SITE = "https://redoceanmap.com"


class _Users:
    def __init__(self, *users: User):
        self.by_id = {u.id: u for u in users}
        self.verified: list[int] = []

    async def find_by_id(self, user_id):
        return self.by_id.get(user_id)

    async def mark_email_verified(self, user_id):
        self.verified.append(user_id)
        self.by_id[user_id] = replace(self.by_id[user_id], email_verified_at=datetime.now(UTC))


class _Tokens:
    def __init__(self, allow=True):
        self.saved: dict[str, tuple[int, str]] = {}
        self.allow = allow
        self.acquired: list[int] = []

    async def save(self, token_hash, user_id, email, ttl):
        assert ttl == policy.TOKEN_TTL
        self.saved[token_hash] = (user_id, email)

    async def consume(self, token_hash):
        return self.saved.pop(token_hash, None)   # 1회용

    async def try_acquire_request(self, user_id, cooldown, daily_limit):
        assert (cooldown, daily_limit) == (policy.REQUEST_COOLDOWN, policy.DAILY_REQUEST_LIMIT)
        self.acquired.append(user_id)
        return self.allow


class _Mail:
    def __init__(self, broken=False):
        self.sent: list[tuple[str, str]] = []
        self.broken = broken

    async def send(self, to_email, link):
        if self.broken:
            raise RuntimeError("n8n down")
        self.sent.append((to_email, link))


def _user(uid=1, email="someone@gmail.com", **kw):
    return User(id=uid, email=email, password_hash="x", name="테스트", **kw)


def _build(*users, allow=True, broken=False):
    repo, tokens, mail = _Users(*users), _Tokens(allow), _Mail(broken)
    return EmailVerificationInteractor(users=repo, tokens=tokens, mail=mail, site_url=SITE), repo, tokens, mail


async def test_인증_메일을_보내고_링크의_토큰으로_인증을_기록한다():
    interactor, repo, tokens, mail = _build(_user())
    assert await interactor.request(1) is VerifyRequestOutcome.SENT
    to, link = mail.sent[0]
    assert to == "someone@gmail.com" and link.startswith(f"{SITE}/verify-email?token=")
    token = link.split("token=", 1)[1]
    assert token not in tokens.saved and policy.token_hash(token) in tokens.saved   # 서버에는 해시만 남는다

    assert await interactor.confirm(token) is True
    assert repo.verified == [1]
    assert await interactor.confirm(token) is False   # 1회용 — 같은 링크를 다시 쓰면 실패


@pytest.mark.parametrize("user, expected", [
    (_user(email_verified_at=datetime(2026, 9, 1, tzinfo=UTC)), VerifyRequestOutcome.ALREADY_VERIFIED),
    (_user(email=None), VerifyRequestOutcome.NO_EMAIL),
    (_user(email="qa.persona05@redoceanmap.com"), VerifyRequestOutcome.UNDELIVERABLE),   # 2026-09-21 사고의 주소
    (_user(email="e2e@example.com"), VerifyRequestOutcome.UNDELIVERABLE),
], ids=["이미 인증", "이메일 없음", "자체 도메인", "예약 도메인"])
async def test_보낼_필요가_없거나_보낼_수_없는_주소에는_메일을_보내지_않는다(user, expected):
    interactor, _, tokens, mail = _build(user)
    assert await interactor.request(1) is expected
    assert mail.sent == [] and tokens.saved == {} and tokens.acquired == []   # 제한 횟수도 쓰지 않는다


async def test_요청_제한에_걸리면_보내지_않는다():
    interactor, _, tokens, mail = _build(_user(), allow=False)
    assert await interactor.request(1) is VerifyRequestOutcome.THROTTLED
    assert mail.sent == [] and tokens.saved == {}


async def test_발송_경로_장애는_예외로_올린다():
    interactor, *_ = _build(_user(), broken=True)
    with pytest.raises(RuntimeError):
        await interactor.request(1)   # 라우터가 503으로 옮긴다 — 서비스 이용은 그대로, 알림 메일 수신만 미뤄진다


@pytest.mark.parametrize("change", [
    {"email": "changed@gmail.com"},                                   # 발급 뒤 주소가 바뀜
    {"deleted_at": datetime(2026, 9, 21, tzinfo=UTC)},               # 탈퇴
    {"suspended_at": datetime(2026, 9, 21, tzinfo=UTC)},             # 정지
], ids=["주소 변경", "탈퇴", "정지"])
async def test_발급_뒤_계정_상태가_달라지면_옛_링크를_인정하지_않는다(change):
    interactor, repo, _, mail = _build(_user())
    await interactor.request(1)
    token = mail.sent[0][1].split("token=", 1)[1]
    repo.by_id[1] = replace(repo.by_id[1], **change)
    assert await interactor.confirm(token) is False and repo.verified == []


async def test_없는_토큰과_빈_토큰은_실패():
    interactor, repo, *_ = _build(_user())
    assert await interactor.confirm("nope") is False and await interactor.confirm("") is False
    assert repo.verified == []


def test_토큰은_추측할_수_없고_해시는_결정적이다():
    a, b = policy.new_token(), policy.new_token()
    assert a != b and len(a) >= 40
    assert policy.token_hash(a) == policy.token_hash(a) != policy.token_hash(b)
    assert policy.verify_link("https://redoceanmap.com/", "T") == "https://redoceanmap.com/verify-email?token=T"
