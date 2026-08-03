"""앱 소유권(app_id) 검증 — 이 검증이 빠지면 타 앱의 유효한 카카오 토큰으로 남의 계정에 들어온다."""
import pytest

from auth.adapter.outbound.gateways import kakao_identity_gateway
from auth.adapter.outbound.gateways.kakao_identity_gateway import KakaoIdentityGateway


@pytest.fixture
def our_app(monkeypatch):
    monkeypatch.setattr(kakao_identity_gateway, "KAKAO_APP_ID", "123456")


def test_우리_앱_토큰은_통과한다(our_app):
    KakaoIdentityGateway._ensure_our_app(123456)  # 카카오는 숫자로 준다 — 문자열 비교로 맞춘다


def test_타_앱에서_발급된_토큰은_거부된다(our_app):
    with pytest.raises(ValueError):
        KakaoIdentityGateway._ensure_our_app(999999)


def test_app_id가_없는_응답도_거부된다(our_app):
    # 응답 형식이 바뀌어 필드가 사라져도 '검증 통과'로 흐르면 안 된다.
    with pytest.raises(ValueError):
        KakaoIdentityGateway._ensure_our_app(None)


def test_앱_id가_설정되지_않았으면_전부_거부된다(monkeypatch):
    monkeypatch.setattr(kakao_identity_gateway, "KAKAO_APP_ID", None)
    with pytest.raises(ValueError):
        KakaoIdentityGateway._ensure_our_app(123456)
