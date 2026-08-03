"""이미지 업로드 인바운드 어댑터 — 멀티파트 HTTP를 app DTO로 바꾸는 것까지가 이 계층의 몫이다.

클라이언트(플러터 게이트웨이·웹) → 이 라우터 → ImageUploadUseCase → ImageStoragePort → S3.
검증·키 생성·저장은 전부 아래 계층이 한다 — 여기서는 바이트를 읽고 예외를 HTTP 상태로 옮긴다.

플러터 쪽 계약: `POST /admin/images`, `multipart/form-data`, 파트 이름 `file`,
`Authorization: Bearer <access token>`(권한 `documents:write`).
파트의 content-type은 무엇이든 상관없다 — 실제 형식은 서버가 바이트로 판정한다.
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from admin.adapter.inbound.api.schemas.s3_image_upload_schema import ImageUploadResponseSchema
from admin.app.dtos.image_upload_dto import ImageUploadCommand, StoredImage
from admin.app.exceptions import ImageStorageUnavailableError, ImageUploadRejectedError
from admin.app.ports.input.image_upload_use_case import ImageUploadUseCase
from admin.dependencies.s3_image_upload_provider import get_image_upload_use_case
from core.security import require_permission

s3_image_upload_router = APIRouter(prefix="/admin", tags=["admin"])


def _to_schema(stored: StoredImage) -> ImageUploadResponseSchema:
    return ImageUploadResponseSchema(
        key=stored.key,
        url=stored.url,
        urlExpiresIn=stored.url_expires_in,
        bucket=stored.bucket,
        contentType=stored.content_type,
        sizeBytes=stored.size_bytes,
    )


@s3_image_upload_router.post(
    "/images",
    response_model=ImageUploadResponseSchema,
    status_code=201,
    summary="이미지 업로드 → S3 저장 → 사전서명 조회 URL 반환",
)
async def upload_image(
    file: UploadFile = File(...),
    actor_id: int = Depends(require_permission("documents:write")),
    use_case: ImageUploadUseCase = Depends(get_image_upload_use_case),
) -> ImageUploadResponseSchema:
    content = await file.read()
    try:
        stored = await use_case.upload(
            ImageUploadCommand(
                actor_id=actor_id,
                filename=file.filename or "unnamed",
                declared_content_type=(file.content_type or "").lower(),
                content=content,
            )
        )
    except ImageUploadRejectedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ImageStorageUnavailableError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return _to_schema(stored)
