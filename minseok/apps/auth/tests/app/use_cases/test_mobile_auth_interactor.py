from datetime import datetime, timezone

import pytest

from auth.app.dtos.mobile_auth_dto import (
    KakaoIdentityDto,
    MobileLoginCommand,
    MobileRefreshSessionDto,
)
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
        self.sessions: dict[tuple[int, str], dict] = {}
        self.denied: set[str] = set()
        self.revoked: list[int] = []

    async def save(self, user_id, jti, device_id, user_agent, expires_at):
        record = {
            "user_id": user_id,
            "jti": jti,
            "device_id": device_id,
            "user_agent": user_agent,
            "expires_at": expires_at,
        }
        self.saved.append(record)
        self.sessions[(user_id, jti)] = record

    async def find(self, user_id, jti):
        record = self.sessions.get((user_id, jti))
        if record is None:
            return None
        return MobileRefreshSessionDto(
            device_id=record["device_id"],
            user_agent=record["user_agent"],
            expires_at=record["expires_at"],
        )

    async def delete(self, user_id, jti):
        self.sessions.pop((user_id, jti), None)

    async def deny(self, jti, expires_at):
        self.denied.add(jti)

    async def is_denied(self, jti):
        return jti in self.denied

    async def revoke_all(self, user_id):
        self.revoked.append(user_id)
        self.sessions = {k: v for k, v in self.sessions.items() if k[0] != user_id}


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


async def test_갱신하면_새_쌍이_나오고_쓴_토큰은_폐기된다():
    refresh = _StubMobileRefreshRepository()
    interactor = _interactor(
        _StubIdentityPort(KakaoIdentityDto(kakao_id=9001)),
        _StubUserRepository([_kakao_user(user_id=7, kakao_id=9001)]),
        refresh,
    )
    issued = await interactor.login_with_kakao(_command())
    old_jti = refresh.saved[0]["jti"]

    renewed = await interactor.refresh(issued.refresh_token)

    assert renewed.status == "ok"
    assert renewed.access_token
    assert renewed.refresh_token != issued.refresh_token  # 회전
    assert (7, old_jti) not in refresh.sessions  # 옛 토큰 폐기
    assert old_jti in refresh.denied  # 재사용 탐지용으로 기억


async def test_갱신해도_기기_정보는_이어진다():
    # 갱신 요청에는 deviceId가 없다 — 저장된 값을 물려주지 않으면 기기 목록이 끊긴다.
    refresh = _StubMobileRefreshRepository()
    interactor = _interactor(
        _StubIdentityPort(KakaoIdentityDto(kakao_id=9001)),
        _StubUserRepository([_kakao_user(user_id=7, kakao_id=9001)]),
        refresh,
    )
    issued = await interactor.login_with_kakao(_command())

    await interactor.refresh(issued.refresh_token)

    assert refresh.saved[-1]["device_id"] == "dev-1"
    assert refresh.saved[-1]["user_agent"] == "app/1.0"


async def test_이미_쓴_토큰을_다시_쓰면_그_유저의_모바일_세션이_전부_끊긴다():
    refresh = _StubMobileRefreshRepository()
    interactor = _interactor(
        _StubIdentityPort(KakaoIdentityDto(kakao_id=9001)),
        _StubUserRepository([_kakao_user(user_id=7, kakao_id=9001)]),
        refresh,
    )
    issued = await interactor.login_with_kakao(_command())
    await interactor.refresh(issued.refresh_token)  # 정상 회전

    with pytest.raises(ValueError):
        await interactor.refresh(issued.refresh_token)  # 사본이 뒤늦게 도착

    assert refresh.revoked == [7]
    assert refresh.sessions == {}  # 회전으로 방금 발급된 세션까지 함께 폐기


async def test_저장에_없는_토큰은_거부하되_전량_폐기까지_가지_않는다():
    refresh = _StubMobileRefreshRepository()
    interactor = _interactor(
        _StubIdentityPort(KakaoIdentityDto(kakao_id=9001)),
        _StubUserRepository([_kakao_user(user_id=7, kakao_id=9001)]),
        refresh,
    )

    with pytest.raises(ValueError):
        await interactor.refresh("7.존재하지않는jti")

    # 만료는 탈취가 아니다 — 남의 user_id를 넣어 세션을 끊는 공격이 성립하면 안 된다.
    assert refresh.revoked == []


async def test_형식이_아닌_리프레시_토큰은_거부된다():
    refresh = _StubMobileRefreshRepository()
    interactor = _interactor(
        _StubIdentityPort(KakaoIdentityDto(kakao_id=9001)), _StubUserRepository(), refresh
    )

    for broken in ["", "점없는토큰", ".jti만", "숫자아님.jti"]:
        with pytest.raises(ValueError):
            await interactor.refresh(broken)

    assert refresh.revoked == []


async def test_정지된_계정은_세션이_살아_있어도_갱신하지_못한다():
    user = _kakao_user(user_id=7, kakao_id=9001)
    repository = _StubUserRepository([user])
    refresh = _StubMobileRefreshRepository()
    interactor = _interactor(
        _StubIdentityPort(KakaoIdentityDto(kakao_id=9001)), repository, refresh
    )
    issued = await interactor.login_with_kakao(_command())
    repository.users[7] = _kakao_user(
        user_id=7, kakao_id=9001, suspended_at=datetime.now(timezone.utc)
    )

    with pytest.raises(ValueError):
        await interactor.refresh(issued.refresh_token)


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
