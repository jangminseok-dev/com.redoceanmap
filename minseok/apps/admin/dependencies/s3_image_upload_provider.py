from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from admin.adapter.outbound.pg.audit_log_pg_adapter import AuditLogPgAdapter
from admin.adapter.outbound.s3_image_storage_adapter import S3ImageStorageAdapter
from admin.app.ports.input.image_upload_use_case import ImageUploadUseCase
from admin.app.ports.output.audit_log_port import AuditLogPort
from admin.app.ports.output.image_storage_port import ImageStoragePort
from admin.app.use_cases.image_upload_interactor import ImageUploadInteractor
from core.config import ADMIN_IMAGE_S3_BUCKET
from core.database import get_db

# S3 어댑터는 무상태(세션 의존 없음)라 프로세스당 1개면 충분하다.
# 버킷 미설정이면 아예 만들지 않는다 — 빈 버킷 이름으로 S3를 때리는 대신 요청 시점에 503으로 알린다.
_storage = S3ImageStorageAdapter(bucket=ADMIN_IMAGE_S3_BUCKET) if ADMIN_IMAGE_S3_BUCKET else None


def get_image_storage_port() -> ImageStoragePort:
    if _storage is None:
        raise HTTPException(
            status_code=503, detail="ADMIN_IMAGE_S3_BUCKET 미설정 — 이미지 업로드를 사용할 수 없습니다."
        )
    return _storage


def get_image_audit_log_port(db: AsyncSession = Depends(get_db)) -> AuditLogPort:
    return AuditLogPgAdapter(session=db)


def get_image_upload_use_case(
    storage: ImageStoragePort = Depends(get_image_storage_port),
    audit: AuditLogPort = Depends(get_image_audit_log_port),
) -> ImageUploadUseCase:
    return ImageUploadInteractor(storage=storage, audit=audit)
