from pydantic import BaseModel, Field


class MobileGatekeeperSchema(BaseModel):

    id: int = Field(0, description="Agent ID")
    name: str = Field("모바일 인증 (auth/mobile)", description="Gatekeeper's name")
    # 앱 전용 로그인 경로 — 카카오 신원 확인 + 자체 JWT 발급

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 1,
                "name": "모바일 인증 (auth/mobile)",
            }
        }
    }


class MobileGatekeeperResponseSchema(BaseModel):

    id: int
    name: str
    introduction: str
