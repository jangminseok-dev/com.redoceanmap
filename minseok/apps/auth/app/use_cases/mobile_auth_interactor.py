import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from auth.app.dtos.mobile_auth_dto import MobileLoginCommand, MobileSessionDto
from auth.app.ports.input.mobile_auth_use_case import MobileAuthUseCase
from auth.app.ports.output.grade_repository import GradeRepository
from auth.app.ports.output.kakao_identity_port import KakaoIdentityPort
from auth.app.ports.output.mobile_refresh_repository import MobileRefreshRepository
from auth.app.ports.output.user_repository import UserRepository
from auth.domain.entities.user_entity import User
from core.config import jwt_private_key

# 웹(15분/7일)보다 길게 잡는다 — 앱은 공용 기기 사용 가능성이 낮고 재로그인 비용이 크다.
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30

PLATFORM = "mobile"


class MobileAuthInteractor(MobileAuthUseCase):
    """모바일 카카오 로그인 — 카카오는 신원 확인에만 쓰고, 세션은 자체 JWT가 유지한다."""

    def __init__(
        self,
        identity_port: KakaoIdentityPort,
        repository: UserRepository,
        refresh_repository: MobileRefreshRepository,
        grades: GradeRepository,
    ) -> None:
        self.identity_port = identity_port
        self.repository = repository
        self.refresh_repository = refresh_repository
        self.grades = grades

    def _unusable_password_hash(self) -> str:
        # 카카오 계정은 비밀번호 로그인 불가 — 아무도 모르는 랜덤 값을 해시해 저장한다.
        return bcrypt.hashpw(secrets.token_urlsafe(32).encode(), bcrypt.gensalt()).decode()

    def _create_access_token(self, user_id: int) -> str:
        # platform 클레임 — 모바일 토큰으로 웹 전용 경로를 부를 수 없게 하는 근거다.
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        return jwt.encode(
            {"sub": str(user_id), "platform": PLATFORM, "exp": expire},
            jwt_private_key(),
            algorithm="RS256",
        )

    async def login_with_kakao(self, command: MobileLoginCommand) -> MobileSessionDto:
        identity = await self.identity_port.verify(command.access_token)
        # 이메일이 아니라 카카오 회원번호로 찾는다 — 이메일은 동의 항목이라 식별자가 될 수 없다.
        user = await self.repository.find_by_kakao_id(identity.kakao_id)
        if user is None:
            if not identity.terms_agreed:
                # 동의 증빙 없이 계정을 만들지 않는다(웹과 동일 원칙) — 앱이 동의 절차를 태워야 한다.
                return MobileSessionDto(status="consent_required")
            user = await self.repository.create(
                identity.email,
                self._unusable_password_hash(),
                identity.nickname or f"카카오{identity.kakao_id}",
                terms_agreed_at=datetime.now(timezone.utc),
                marketing_agreed=identity.marketing_agreed,
                kakao_id=identity.kakao_id,
            )
            await self.grades.grant_basic(user.id)
        user.ensure_active()  # 정지/탈퇴 계정 거부
        await self.repository.touch_last_login(user.id)
        return await self._issue_session(user, command)

    async def _issue_session(self, user: User, command: MobileLoginCommand) -> MobileSessionDto:
        expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        jti = secrets.token_urlsafe(48)
        await self.refresh_repository.save(
            user_id=user.id,
            jti=jti,
            device_id=command.device_id,
            user_agent=command.user_agent,
            expires_at=expires_at,
        )
        return MobileSessionDto(
            status="ok",
            access_token=self._create_access_token(user.id),
            # 저장 키가 `mobile:refresh:{user_id}:{jti}`라 갱신 때 user_id가 필요하다 —
            # 토큰 자체에 실어 보낸다(비밀은 jti뿐이고, user_id는 본인 것이다).
            refresh_token=f"{user.id}.{jti}",
        )
