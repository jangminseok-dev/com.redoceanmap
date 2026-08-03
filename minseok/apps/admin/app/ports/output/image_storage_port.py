from __future__ import annotations

from abc import ABC, abstractmethod

from admin.app.dtos.image_upload_dto import StoredImage


class ImageStoragePort(ABC):
    """이미지 객체 저장 아웃바운드 포트 — 정해진 키로 저장하고 조회 URL을 돌려준다.

    구현(S3)은 어댑터 계층에만 존재한다. app 계층은 "키·바이트를 주면 저장되고
    한시적 조회 URL이 나온다"는 계약만 안다 — boto3도 버킷 설정도 여기서는 보이지 않는다.
    키 명명은 도메인 정책(`image_upload_policy`)이 이미 정하므로 이 계약의 몫이 아니다.
    """

    @abstractmethod
    async def put_image(self, key: str, content: bytes, content_type: str) -> StoredImage:
        """객체를 저장한다. 저장소 접근이 실패하면 ImageStorageUnavailableError."""
        ...
