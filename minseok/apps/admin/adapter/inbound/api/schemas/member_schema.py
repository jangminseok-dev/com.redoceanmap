from datetime import datetime

from pydantic import BaseModel, Field


class MemberSchema(BaseModel):
    id: int
    email: str | None  # 카카오 모바일 가입 회원은 이메일이 없다(선택 동의)
    name: str
    joined_at: datetime | None
    marketing_agreed: bool
    roles: list[str]
    suspended_at: datetime | None = None
    deleted_at: datetime | None = None


class MemberListResponseSchema(BaseModel):
    total: int
    items: list[MemberSchema]


class RoleSchema(BaseModel):
    code: str
    name: str
    permissions: list[str]


class RoleListResponseSchema(BaseModel):
    roles: list[RoleSchema]


class RoleGrantRequestSchema(BaseModel):
    role_code: str


class SuspendRequestSchema(BaseModel):
    reason: str = Field("", max_length=200)  # users.suspended_reason 컬럼 폭과 일치


class SessionRevokeResponseSchema(BaseModel):
    revoked: int
