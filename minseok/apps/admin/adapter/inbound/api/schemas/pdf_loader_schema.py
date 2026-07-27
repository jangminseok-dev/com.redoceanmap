from datetime import datetime

from pydantic import BaseModel


class PdfDocumentSchema(BaseModel):
    id: int
    filename: str
    title: str
    summary: str
    charCount: int
    createdAt: datetime


class PdfListResponseSchema(BaseModel):
    items: list[PdfDocumentSchema]


class PdfDetailResponseSchema(BaseModel):
    document: PdfDocumentSchema
    text: str  # 추출 원문 전문
