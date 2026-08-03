from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImageUploadCommand:
    """이미지 업로드 요청 — 라우터가 UploadFile을 읽어 바이트로 넘긴다.

    `filename`·`declared_content_type`은 클라이언트가 준 값이라 저장 판단에 쓰지 않는다
    (감사 기록에만 남는다). 실제 형식은 도메인 정책이 바이트에서 판정한다.
    """

    actor_id: int
    filename: str
    declared_content_type: str
    content: bytes


@dataclass(frozen=True)
class StoredImage:
    """저장 결과 — 객체 키와 조회용 URL(만료 있음)."""

    key: str
    url: str
    url_expires_in: int
    bucket: str
    content_type: str
    size_bytes: int
