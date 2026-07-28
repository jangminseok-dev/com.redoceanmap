"""가입·로그인 입력 정책 — 이메일 형식, 최소 길이, bcrypt 72바이트 상한.

상한 검증이 있는 이유: bcrypt 5.0은 72바이트 초과를 잘라내지 않고 ValueError를 던진다.
스키마에서 막지 않으면 긴 비밀번호로 가입할 때 500이 난다(2026-07-28 보안 점검).
"""
import pytest
from pydantic import ValidationError

from auth.adapter.inbound.api.schemas.auth_schema import LoginRequest, RegisterRequest


def _register(password: str = "충분히긴비밀번호12", email: str = "user@test.com") -> RegisterRequest:
    return RegisterRequest(email=email, password=password, name="테스터", terms_agreed=True)


def test_정상_가입_요청은_통과한다():
    assert _register().email == "user@test.com"


def test_짧은_비밀번호는_거부된다():
    with pytest.raises(ValidationError):
        _register(password="short123")


def test_bcrypt_상한을_넘는_비밀번호는_거부된다():
    한글25자 = "가" * 25  # 75바이트 — 문자 수만 세면 통과해버린다
    assert len(한글25자.encode()) > 72
    with pytest.raises(ValidationError):
        _register(password=한글25자)


def test_이메일_형식을_검증한다():
    with pytest.raises(ValidationError):
        _register(email="not-an-email")


def test_로그인은_짧은_비밀번호와_구형_주소를_받는다():
    """정책 도입 전 가입자를 잠그지 않는다 — 길이·형식 검증은 가입에만 건다."""
    old = LoginRequest(email="t@t.local", password="1234")
    assert old.password == "1234" and old.email == "t@t.local"


def test_로그인도_bcrypt_상한은_지킨다():
    with pytest.raises(ValidationError):
        LoginRequest(email="t@t.local", password="가" * 25)
