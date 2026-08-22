from __future__ import annotations

from hub.app.ports.output.member_contact_port import MemberContactPort


def get_member_contact_port() -> MemberContactPort:
    """합성 루트(main.py)의 dependency_overrides로 스포크(auth) 구현을 주입한다."""
    raise NotImplementedError(
        "get_member_contact_port는 main.py의 dependency_overrides로 auth 구현을 주입해야 합니다."
    )
