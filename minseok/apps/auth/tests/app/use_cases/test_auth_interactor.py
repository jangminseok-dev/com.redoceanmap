from datetime import datetime, timedelta, timezone

import pytest

from auth.app.use_cases.auth_interactor import AuthInteractor
from auth.domain.entities.refresh_token_entity import RefreshToken, RotatedRefreshToken
from auth.domain.entities.user_entity import User


class _StubUserRepository:
    def __init__(self):
        self.users: dict[int, User] = {}
        self._seq = 0

    async def find_by_email(self, email):
        return next((u for u in self.users.values() if u.email == email), None)

    async def find_by_id(self, user_id):
        return self.users.get(user_id)

    async def create(self, email, password_hash, name, terms_agreed_at=None, marketing_agreed=False):
        self._seq += 1
        user = User(
            id=self._seq,
            email=email,
            password_hash=password_hash,
            name=name,
            terms_agreed_at=terms_agreed_at,
            marketing_agreed=marketing_agreed,
        )
        self.users[user.id] = user
        return user


class _StubRefreshTokenRepository:
    def __init__(self):
        self.tokens: dict[str, RefreshToken] = {}
        self.rotated: dict[str, RotatedRefreshToken] = {}

    async def create(self, user_id, token, expires_at):
        entity = RefreshToken(user_id=user_id, token=token, expires_at=expires_at)
        self.tokens[token] = entity
        return entity

    async def find_by_token(self, token):
        return self.tokens.get(token)

    async def delete(self, token):
        self.tokens.pop(token, None)

    async def mark_rotated(self, token):
        self.rotated[token.token] = RotatedRefreshToken(
            user_id=token.user_id, rotated_at=datetime.now(timezone.utc)
        )

    async def find_rotated(self, token):
        return self.rotated.get(token)

    async def delete_all_for_user(self, user_id):
        doomed = [t for t, e in self.tokens.items() if e.user_id == user_id]
        for t in doomed:
            del self.tokens[t]
        return len(doomed)


class _StubGradeRepository:
    def __init__(self, basic_tabs=("history", "market"), tabs_by_user=None):
        self.granted: list[int] = []
        self.basic_tabs = list(basic_tabs)
        self.tabs_by_user = tabs_by_user or {}

    async def grant_basic(self, user_id):
        self.granted.append(user_id)

    async def visible_tabs(self, user_id):
        if user_id is None:
            return self.basic_tabs
        return self.tabs_by_user.get(user_id, self.basic_tabs)


def _interactor():
    return AuthInteractor(
        repository=_StubUserRepository(),
        refresh_repository=_StubRefreshTokenRepository(),
        grades=_StubGradeRepository(),
    )


async def test_가입은_액세스와_리프레시_토큰_쌍을_발급한다():
    interactor = _interactor()
    result = await interactor.register("a@b.c", "pw1234", "장민석")
    assert result.access_token
    assert result.refresh_token
    assert result.email == "a@b.c"
    assert result.refresh_token in interactor.refresh_repository.tokens


async def test_가입은_필수_약관_동의_시각을_기록한다():
    interactor = _interactor()
    await interactor.register("a@b.c", "pw1234", "장민석", terms_agreed=True, marketing_agreed=True)
    user = await interactor.repository.find_by_email("a@b.c")
    assert user.terms_agreed_at is not None
    assert user.marketing_agreed is True


async def test_필수_약관_미동의_가입은_거부된다():
    interactor = _interactor()
    with pytest.raises(ValueError):
        await interactor.register("a@b.c", "pw1234", "장민석", terms_agreed=False)


async def test_중복_이메일_가입은_거부된다():
    interactor = _interactor()
    await interactor.register("a@b.c", "pw1234", "장민석")
    with pytest.raises(ValueError):
        await interactor.register("a@b.c", "pw5678", "다른사람")


async def test_로그인은_비밀번호가_틀리면_거부된다():
    interactor = _interactor()
    await interactor.register("a@b.c", "pw1234", "장민석")
    with pytest.raises(ValueError):
        await interactor.login("a@b.c", "틀린비번")
    result = await interactor.login("a@b.c", "pw1234")
    assert result.access_token


async def test_리프레시는_회전한다_사용한_토큰은_재사용_불가():
    interactor = _interactor()
    first = await interactor.register("a@b.c", "pw1234", "장민석")
    renewed = await interactor.refresh(first.refresh_token)
    assert renewed.refresh_token != first.refresh_token
    with pytest.raises(ValueError):  # 이미 회전(폐기)된 토큰
        await interactor.refresh(first.refresh_token)


async def test_유예_안의_재사용은_거절만_하고_세션을_끊지_않는다():
    # 액세스 만료 순간 여러 요청이 동시에 갱신을 시도하는 정상 상황
    interactor = _interactor()
    first = await interactor.register("a@b.c", "pw1234", "장민석")
    renewed = await interactor.refresh(first.refresh_token)
    with pytest.raises(ValueError):
        await interactor.refresh(first.refresh_token)
    assert renewed.refresh_token in interactor.refresh_repository.tokens


async def test_유예_뒤의_재사용은_탈취로_보고_그_유저의_웹_세션을_전부_끊는다():
    interactor = _interactor()
    first = await interactor.register("a@b.c", "pw1234", "장민석")
    other_device = await interactor.login("a@b.c", "pw1234")
    renewed = await interactor.refresh(first.refresh_token)
    repo = interactor.refresh_repository
    repo.rotated[first.refresh_token] = RotatedRefreshToken(
        user_id=1, rotated_at=datetime.now(timezone.utc) - timedelta(minutes=5)
    )

    with pytest.raises(ValueError):
        await interactor.refresh(first.refresh_token)

    assert renewed.refresh_token not in repo.tokens
    assert other_device.refresh_token not in repo.tokens


async def test_만료된_리프레시_토큰은_거부되고_폐기된다():
    interactor = _interactor()
    result = await interactor.register("a@b.c", "pw1234", "장민석")
    expired = RefreshToken(
        user_id=1,
        token=result.refresh_token,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    interactor.refresh_repository.tokens[result.refresh_token] = expired
    with pytest.raises(ValueError):
        await interactor.refresh(result.refresh_token)
    assert result.refresh_token not in interactor.refresh_repository.tokens


async def test_알_수_없는_리프레시_토큰은_거부된다():
    interactor = _interactor()
    with pytest.raises(ValueError):
        await interactor.refresh("없는토큰")


async def test_정지된_계정은_로그인과_리프레시가_거부된다():
    from dataclasses import replace

    repo = _StubUserRepository()
    refresh_repo = _StubRefreshTokenRepository()
    interactor = AuthInteractor(
        repository=repo, refresh_repository=refresh_repo, grades=_StubGradeRepository()
    )
    tokens = await interactor.register("ban@b.c", "pw1234", "정지자")
    repo.users[1] = replace(repo.users[1], suspended_at=datetime.now(timezone.utc))

    with pytest.raises(ValueError):
        await interactor.login("ban@b.c", "pw1234")
    with pytest.raises(ValueError):
        await interactor.refresh(tokens.refresh_token)


async def test_가입_시_기본_등급이_자동_부여된다():
    interactor = _interactor()
    await interactor.register("a@b.c", "pw1234", "장민석")
    assert interactor.grades.granted == [1]


async def test_get_tabs는_비로그인이면_기본_등급_탭을_반환한다():
    interactor = _interactor()
    assert await interactor.get_tabs(None) == ["history", "market"]


async def test_get_tabs는_무효_토큰도_비로그인과_동일하게_처리한다():
    interactor = _interactor()
    assert await interactor.get_tabs("깨진토큰") == ["history", "market"]


async def test_get_tabs는_유효_토큰이면_유저_등급_탭_합집합을_반환한다():
    grades = _StubGradeRepository(tabs_by_user={1: ["history", "market", "stock", "vision"]})
    interactor = AuthInteractor(
        repository=_StubUserRepository(),
        refresh_repository=_StubRefreshTokenRepository(),
        grades=grades,
    )
    tokens = await interactor.register("a@b.c", "pw1234", "장민석")
    assert await interactor.get_tabs(tokens.access_token) == [
        "history", "market", "stock", "vision",
    ]


async def test_정지된_계정은_get_me가_None을_반환한다():
    from dataclasses import replace

    repo = _StubUserRepository()
    interactor = AuthInteractor(
        repository=repo,
        refresh_repository=_StubRefreshTokenRepository(),
        grades=_StubGradeRepository(),
    )
    tokens = await interactor.register("ban2@b.c", "pw1234", "정지자")
    repo.users[1] = replace(repo.users[1], suspended_at=datetime.now(timezone.utc))

    assert await interactor.get_me(tokens.access_token) is None
