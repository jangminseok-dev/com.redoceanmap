from __future__ import annotations

from abc import ABC, abstractmethod

from admin.app.dtos.image_upload_dto import ImageUploadCommand, StoredImage


class ImageUploadUseCase(ABC):
    """이미지 업로드 → 정책 검증 → 객체 저장 → 감사 기록 파이프라인 유스케이스."""

    @abstractmethod
    async def upload(self, command: ImageUploadCommand) -> StoredImage:
        """이미지를 저장하고 객체 키·조회 URL을 반환한다.

        정책 위반은 ImageUploadRejectedError, 저장소 실패는 ImageStorageUnavailableError.
        """
        ...
