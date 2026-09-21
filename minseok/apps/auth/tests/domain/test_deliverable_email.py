"""발송 가능 주소 판정 — QA 계정으로 나간 알림의 반송 안내가 받은편지함을 채운 사고(2026-09-21)의 회귀 방지."""
import pytest

from auth.domain.value_objects.deliverable_email import is_deliverable


@pytest.mark.parametrize("email", [
    "jang971121@gmail.com", "someone@naver.com", "user.name+tag@company.co.kr", "Dev@LangTailor.com",
])
def test_실제_수신자가_있을_수_있는_주소는_보낸다(email):
    assert is_deliverable(email)


@pytest.mark.parametrize("email", [
    "qa.persona05@redoceanmap.com",     # 사고의 주소 — 자체 도메인에는 메일함이 없다
    "QA.Persona07@RedOceanMap.com",     # 대소문자 무관
    "e2e-bookmark2@example.com",        # 예약 도메인(RFC 2606)
    "tester@test.local", "a@b.test", "x@y.invalid",   # 예약 최상위 도메인
    "root@localhost", "no-at-sign", "two@@signs.com", "@nolocal.com", "", None,
])
def test_받을_수_없는_주소는_발송_대상에서_뺀다(email):
    assert not is_deliverable(email)
