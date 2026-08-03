from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from admin.app.dtos.image_upload_dto import ImageUploadCommand, StoredImage
from admin.app.exceptions import ImageUploadRejectedError
from admin.app.ports.input.image_upload_use_case import ImageUploadUseCase
from admin.app.ports.output.audit_log_port import AuditLogPort
from admin.app.ports.output.image_storage_port import ImageStoragePort
from admin.domain.services.image_upload_policy import build_object_key, inspect


class ImageUploadInteractor(ImageUploadUseCase):
    """이미지 업로드 대장 — 정책 판정 → 키 생성 → 저장 → 감사 기록 순으로 조립한다.

    판정 규칙은 도메인(순수)이, 저장은 아웃바운드 포트가 맡는다. 이 계층에는
    S3도 HTTP도 없다 — 클라이언트가 플러터든 웹이든 이 파이프라인은 같다.
    감사는 admin 규칙대로 '변경 행위'인 업로드에만 남긴다.
    """

    def __init__(self, storage: ImageStoragePort, audit: AuditLogPort) -> None:
        self._storage = storage
        self._audit = audit

    async def upload(self, command: ImageUploadCommand) -> StoredImage:
        verdict = inspect(command.content)
        if verdict.reason or verdict.content_type is None:
            raise ImageUploadRejectedError(verdict.reason or "이미지를 받아들일 수 없습니다.")

        key = build_object_key(
            content_type=verdict.content_type,
            unique_id=uuid4().hex,
            uploaded_at=datetime.now(timezone.utc),
        )
        stored = await self._storage.put_image(
            key=key, content=command.content, content_type=verdict.content_type
        )
        # 원본 파일명은 객체 키에 없다 — 어느 파일이 어느 키가 됐는지는 이 기록에만 남는다.
        await self._audit.write(
            actor_id=command.actor_id,
            action="image.upload",
            detail=(
                f"key={stored.key} file={command.filename} "
                f"type={stored.content_type} bytes={stored.size_bytes}"
            ),
        )
        return stored
