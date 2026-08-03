import httpx

from auth.adapter.outbound.gateways.social_oauth_gateway import (
    KAKAO_MARKETING_TAG,
    KAKAO_REQUIRED_TAGS,
)
from auth.app.dtos.mobile_auth_dto import KakaoIdentityDto
from auth.app.ports.output.kakao_identity_port import KakaoIdentityPort
from core.config import KAKAO_APP_ID

# 실패 사유를 세분해 노출하지 않는다 — "미가입"과 "토큰 무효"를 구분해 알려주면 계정 존재 여부가 샌다.
LOGIN_FAILED = "카카오 로그인에 실패했습니다. 다시 시도해 주세요."

_TOKEN_INFO_URL = "https://kapi.kakao.com/v1/user/access_token_info"
_ME_URL = "https://kapi.kakao.com/v2/user/me"
_SERVICE_TERMS_URL = "https://kapi.kakao.com/v2/user/service_terms"


class KakaoIdentityGateway(KakaoIdentityPort):
    """카카오 액세스 토큰 → 회원번호·프로필. 앱 소유권(app_id)을 먼저 확인한다."""

    async def verify(self, access_token: str) -> KakaoIdentityDto:
        if not KAKAO_APP_ID:
            raise ValueError("카카오 로그인이 설정되지 않았습니다. (KAKAO_APP_ID)")
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=10) as client:
            # app_id는 /v2/user/me가 아니라 이 엔드포인트에만 있다 — 순서를 바꾸면 소유권 검증이 빠진다.
            info = await client.get(_TOKEN_INFO_URL, headers=headers)
            if info.status_code != 200:
                raise ValueError(LOGIN_FAILED)
            payload = info.json()
            self._ensure_our_app(payload.get("app_id"))
            kakao_id = int(payload["id"])

            me = await client.get(_ME_URL, headers=headers)
            terms = await client.get(
                _SERVICE_TERMS_URL,
                params={"result": "app_service_terms"},
                headers=headers,
            )

        account = (me.json() if me.status_code == 200 else {}).get("kakao_account") or {}
        agreed = self._agreed_tags(terms)
        return KakaoIdentityDto(
            kakao_id=kakao_id,
            email=account.get("email"),  # 선택 동의 — 없으면 None으로 가입한다
            nickname=(account.get("profile") or {}).get("nickname"),
            terms_agreed=KAKAO_REQUIRED_TAGS <= agreed,
            marketing_agreed=KAKAO_MARKETING_TAG in agreed,
        )

    @staticmethod
    def _ensure_our_app(app_id: object) -> None:
        """타 앱에서 발급된 토큰 차단.

        이 검증이 없으면 공격자가 자기 앱에서 받은 유효한 카카오 토큰으로 남의 계정에 로그인할 수 있다.
        """
        if app_id is None or str(app_id) != str(KAKAO_APP_ID):
            raise ValueError(LOGIN_FAILED)

    @staticmethod
    def _agreed_tags(response: httpx.Response) -> set[str]:
        """카카오싱크 동의 태그 — 조회 실패는 '동의 없음'으로 본다(자체 동의 절차로 넘긴다)."""
        if response.status_code != 200:
            return set()
        terms = response.json().get("service_terms") or []
        return {t.get("tag") for t in terms if t.get("agreed")}
