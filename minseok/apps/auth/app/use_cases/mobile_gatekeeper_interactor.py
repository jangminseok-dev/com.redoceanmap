from __future__ import annotations

import logging

from auth.app.dtos.mobile_gatekeeper_dto import (
    MobileGatekeeperQuery,
    MobileGatekeeperResponse,
)
from auth.app.ports.input.mobile_gatekeeper_use_case import MobileGatekeeperUseCase
from auth.app.ports.output.mobile_gatekeeper_record_port import MobileGatekeeperRecordPort

logger = logging.getLogger(__name__)


class MobileGatekeeperInteractor(MobileGatekeeperUseCase):
    """모바일 인증 (auth/mobile) 대장 — 자기소개. 담당: 앱 전용 로그인 경로."""

    def __init__(self, record: MobileGatekeeperRecordPort) -> None:
        self._record = record

    async def introduce_myself(
        self, query: MobileGatekeeperQuery
    ) -> MobileGatekeeperResponse:
        await self._record.record(
            subject="introduce_myself", note=f"{query.name} 자기소개 관찰"
        )
        return MobileGatekeeperResponse(
            id=query.id,
            name=query.name,
            introduction=(
                "Flutter 앱 전용 로그인 경로입니다. "
                "POST /auth/mobile/kakao 로 카카오 액세스 토큰을 받아 서버가 카카오에 신원을 직접 확인하고, "
                "자체 JWT(platform=mobile)를 발급합니다. "
                "리프레시 토큰은 Redis 모바일 DB(db 1)에 기기 정보와 함께 저장합니다. "
                "클라이언트가 보낸 프로필은 신뢰하지 않으며, 카카오 토큰은 저장하지 않습니다. "
                "쿠키를 쓰지 않습니다 — 토큰은 응답 본문으로만 내려갑니다."
            ),
        )
