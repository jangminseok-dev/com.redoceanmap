from pydantic import BaseModel


class ImageUploadResponseSchema(BaseModel):
    key: str
    url: str  # 사전서명 조회 URL — urlExpiresIn 초 뒤 만료
    urlExpiresIn: int
    bucket: str
    contentType: str
    sizeBytes: int
