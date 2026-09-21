"""발송 가능한 이메일 주소인가 — 순수 판정(2026-09-21).

QA 테스트 계정(qa.persona05·07@redoceanmap.com)이 9/8에 NVDA·TSLA·AAPL을 북마크한 뒤 매시간 뉴스 알림 대상이 됐다.
그 주소에는 메일함이 없어 Gmail이 "전송이 완료되지 않음" 안내를 발신 계정으로 되돌려 보냈고, 받은편지함이 수백 통으로 찼다.
알림 수신 설정은 기본값이 '수신'이라 테스트 계정을 새로 만들 때마다 재발한다 — 발송 주소를 모으는 단일 지점
(MemberContactGateway)에서 받을 수 없는 주소를 걸러 구조적으로 막는다.
"""
from __future__ import annotations

# 서비스 자체 도메인 — 메일함을 운영하지 않는다. QA·E2E 계정이 이 도메인을 쓴다.
# 이 도메인으로 실제 메일을 받기 시작하면 여기서 빼야 한다.
OWN_DOMAINS = frozenset({"redoceanmap.com"})
# 문서·테스트용 예약 도메인(RFC 2606·6761) — 실제 수신자가 있을 수 없다
RESERVED_DOMAINS = frozenset({"example.com", "example.org", "example.net", "localhost"})
RESERVED_TLDS = frozenset({"test", "local", "invalid", "example", "localhost"})


def is_deliverable(email: str | None) -> bool:
    """알림 메일을 보내도 되는 주소인가. 형식이 깨진 주소·예약 도메인·자체 도메인은 False."""
    if not email or email.count("@") != 1:
        return False
    local, domain = email.strip().lower().rsplit("@", 1)
    if not local or "." not in domain:
        return False
    if domain in OWN_DOMAINS or domain in RESERVED_DOMAINS:
        return False
    return domain.rsplit(".", 1)[-1] not in RESERVED_TLDS
