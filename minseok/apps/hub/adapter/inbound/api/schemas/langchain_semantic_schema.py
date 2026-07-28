from pydantic import BaseModel, Field


class LangchainAskSchema(BaseModel):

    prompt: str = Field(..., min_length=1, description="사용자 질문")
    sessionId: int | None = Field(
        default=None, description="이어갈 대화 세션 id. 없으면 새 세션을 연다"
    )

    model_config = {
        "json_schema_extra": {
            "example": {"prompt": "성수동 카페 상권 요즘 어때?", "sessionId": None}
        }
    }


class LangchainAskResponseSchema(BaseModel):

    sessionId: int
    destination: str
    entities: list[str]
    answer: str
    chain: str


class LangchainSemanticResponseSchema(BaseModel):

    id: int
    name: str
    introduction: str
