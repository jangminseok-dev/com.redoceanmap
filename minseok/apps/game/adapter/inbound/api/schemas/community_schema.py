from datetime import datetime

from pydantic import BaseModel, Field


class CommentSchema(BaseModel):

    id: int
    author: str = Field(
        description="user_id에서 유도한 결정론 가명 — 실명·이메일이 아니다"
    )
    body: str
    createdTick: int
    createdAt: datetime
    mine: bool = Field(description="조회자 본인이 쓴 것 — 삭제 버튼이 붙는 자리")
    holdsSymbol: bool = Field(
        description="작성자가 **지금** 이 종목의 열린 포지션을 가지고 있다"
    )


class PostSchema(BaseModel):

    id: int
    author: str
    body: str
    createdTick: int
    createdAt: datetime
    mine: bool
    holdsSymbol: bool
    comments: list[CommentSchema]


class ThreadResponseSchema(BaseModel):

    symbol: str
    name: str = Field(description="가상 회사명 — 실재 기업이 아니다")
    posts: list[PostSchema]


class WritePostRequestSchema(BaseModel):

    symbol: str
    body: str


class WriteCommentRequestSchema(BaseModel):

    body: str


class ReportRequestSchema(BaseModel):

    targetType: str = Field(description="post | comment")
    targetId: int
    reason: str = Field(description="신고 사유. 접수만 하며 이 요청으로 글이 내려가지 않는다")


class PostReceiptSchema(BaseModel):

    id: int
    createdTick: int


class CommunityMyselfSchema(BaseModel):

    name: str
    introduction: str
    endpoints: list[str]
    constraints: list[str]
