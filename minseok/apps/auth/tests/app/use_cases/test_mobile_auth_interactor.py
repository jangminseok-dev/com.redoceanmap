from datetime import datetime, timezone

import pytest

from auth.app.dtos.mobile_auth_dto import KakaoIdentityDto, MobileLoginCommand
from auth.app.use_cases.mobile_auth_interactor import MobileAuthInteractor
from auth.domain.entities.user_entity import User


class _StubIdentityPort:
    def __init__(self, identity: KakaoIdentityDto | None = None):
        self.identity = identity
        self.seen: list[str] = []

    async def verify(self, access_token):
        self.seen.append(access_token)
        if self.identity is None:  # 타 앱 토큰·만료 토큰이 여기로 온다
            raise ValueError("카카오 로그인에 실패했습니다. 다시 시도해 주세요.")
        return self.identity


class _StubUserRepository:
    def __init__(self, users: list[User] | None = None):
        self.users: dict[int, User] = {u.id: u for u in (users or [])}
        self._seq = len(self.users)
        self.touched: list[int] = []

    async def find_by_email(self, email):
        return next((u for u in self.users.values() if u.email == email), None)

    async def find_by_id(self, user_id):
        return self.users.get(user_id)

    async def find_by_kakao_id(self, kakao_id):
        return next((u for u in self.users.values() if u.kakao_id == kakao_id), None)

    async def create(
        self,
        email,
        password_hash,
        name,
        terms_agreed_at=None,
        marketing_agreed=False,
        kakao_id=None,
    ):
        self._seq += 1
        user = User(
            id=self._seq,
            email=email,
            password_hash=password_hash,
            name=name,
            kakao_id=kakao_id,
            terms_agreed_at=terms_agreed_at,
            marketing_agreed=marketing_agreed,
        )
        self.users[user.id] = user
        return user

    async def touch_last_login(self, user_id):
        self.touched.append(user_id)


class _StubMobileRefreshRepository:
    def __init__(self):
        self.saved: list[dict] = []

    async def save(self, user_id, jti, device_id, user_agent, expires_at):
        self.saved.append(
            {
                "user_id": user_id,
                "jti": jti,
                "device_id": device_id,
                "user_agent": user_agent,
                "expires_at": expires_at,
            }
        )


class _StubGradeRepository:
    def __init__(self):
        self.granted: list[int] = []

    async def grant_basic(self, user_id):
        self.granted.append(user_id)

    async def visible_tabs(self, user_id):
        return []


def _interactor(identity_port, repository, refresh=None, grades=None):
    return MobileAuthInteractor(
        identity_port=identity_port,
        repository=repository,
        refresh_repository=refresh or _StubMobileRefreshRepository(),
        grades=grades or _StubGradeRepository(),
    )


def _command():
    return MobileLoginCommand(access_token="kakao-token", device_id="dev-1", user_agent="app/1.0")


def _kakao_user(user_id: int = 1, kakao_id: int = 9001, **kwargs) -> User:
    return User(
        id=user_id,
        email=kwargs.get("email", "user@example.com"),
        password_hash="x",
        name="사용자",
        kakao_id=kakao_id,
        terms_agreed_at=datetime.now(timezone.utc),
        **{k: v for k, v in kwargs.items() if k != "email"},
    )


async def test_카카오_검증에_실패하면_로그인이_거부된다():
    interactor = _interactor(_StubIdentityPort(None), _StubUserRepository())
    with pytest.raises(ValueError):
        await interactor.login_with_kakao(_command())


async def test_기존_유저는_카카오_회원번호로_찾는다():
    repository = _StubUserRepository([_kakao_user(kakao_id=9001)])
    refresh = _StubMobileRefreshRepository()
    grades = _StubGradeRepository()
    interactor = _interactor(
        _StubIdentityPort(KakaoIdentityDto(kakao_id=9001, email="다른@example.com")),
        repository,
        refresh,
        grades,
    )

    result = await interactor.login_with_kakao(_command())

    assert result.status == "ok"
    assert result.access_token
    assert grades.granted == []  # 신규 가입이 아니다
    assert repository.touched == [1]
    assert refresh.saved[0]["user_id"] == 1


async def test_이메일_동의를_안_해도_신규_가입된다():
    # 카카오 이메일은 선택 동의라 없을 수 있다 — 식별자는 kakao_id다.
    repository = _StubUserRepository()
    grades = _StubGradeRepository()
    interactor = _interactor(
        _StubIdentityPort(
            KakaoIdentityDto(kakao_id=9002, email=None, nickname="홍길동", terms_agreed=True)
        ),
        repository,
        grades=grades,
    )

    result = await interactor.login_with_kakao(_command())

    created = repository.users[1]
    assert result.status == "ok"
    assert created.email is None
    assert created.kakao_id == 9002
    assert created.name == "홍길동"
    assert created.terms_agreed_at is not None  # 동의 증빙 없이 계정을 만들지 않는다
    assert grades.granted == [1]


async def test_필수_약관_미동의_신규_유저는_가입하지_않고_동의를_요구한다():
    repository = _StubUserRepository()
    interactor = _interactor(
        _StubIdentityPort(KakaoIdentityDto(kakao_id=9003, terms_agreed=False)), repository
    )

    result = await interactor.login_with_kakao(_command())

    assert result.status == "consent_required"
    assert result.access_token is None
    assert repository.users == {}


async def test_리프레시_토큰은_기기_정보와_함께_저장되고_user_id를_앞에_붙여_내려간다():
    refresh = _StubMobileRefreshRepository()
    interactor = _interactor(
        _StubIdentityPort(KakaoIdentityDto(kakao_id=9001)),
        _StubUserRepository([_kakao_user(user_id=7, kakao_id=9001)]),
        refresh,
    )

    result = await interactor.login_with_kakao(_command())

    saved = refresh.saved[0]
    assert saved["device_id"] == "dev-1"
    assert saved["user_agent"] == "app/1.0"
    # 갱신 때 `mobile:refresh:{user_id}:{jti}` 키를 곧장 찾을 수 있어야 한다.
    assert result.refresh_token == f"7.{saved['jti']}"


async def test_정지된_계정은_모바일_로그인도_거부된다():
    suspended = _kakao_user(kakao_id=9001, suspended_at=datetime.now(timezone.utc))
    interactor = _interactor(
        _StubIdentityPort(KakaoIdentityDto(kakao_id=9001)), _StubUserRepository([suspended])
    )

    with pytest.raises(ValueError):
        await interactor.login_with_kakao(_command())


async def test_액세스_토큰에_platform_클레임이_들어간다():
    # 서명 검증이 아니라 클레임 내용을 보는 테스트다 — 키 쌍 검증은 환경(.env)의 몫이다.
    from jose import jwt

    interactor = _interactor(
        _StubIdentityPort(KakaoIdentityDto(kakao_id=9001)),
        _StubUserRepository([_kakao_user(user_id=3, kakao_id=9001)]),
    )

    result = await interactor.login_with_kakao(_command())

    payload = jwt.get_unverified_claims(result.access_token)
    assert payload["platform"] == "mobile"
    assert payload["sub"] == "3"
