"""업로드 이미지를 S3에 올리고 조회용 사전서명 URL을 돌려주는 어댑터.

boto3는 동기 클라이언트라 put·presign을 한 번의 `asyncio.to_thread`로 묶어 이벤트 루프를
막지 않는다(백엔드 async 규칙). 클라이언트는 **첫 호출 때** 만든다 —
`s3_client()`가 AWS 키를 `require`하므로 모듈 로드 시점에 만들면 키가 없는 환경에서
백엔드 기동 자체가 죽는다(이미지 업로드만 못 쓰면 되는 상황이다).

버킷은 비공개 전제라 공개 URL 대신 사전서명 URL을 돌려준다.
"""

from __future__ import annotations

import asyncio

from botocore.exceptions import BotoCoreError, ClientError

from admin.app.dtos.image_upload_dto import StoredImage
from admin.app.exceptions import ImageStorageUnavailableError
from admin.app.ports.output.image_storage_port import ImageStoragePort
from core.key.s3_manager import s3_client

DEFAULT_URL_EXPIRES_IN = 900  # 15분 — 어드민이 업로드 직후 확인하는 용도


class S3ImageStorageAdapter(ImageStoragePort):
    """ImageStoragePort의 S3 구현."""

    def __init__(self, bucket: str, url_expires_in: int = DEFAULT_URL_EXPIRES_IN) -> None:
        self._bucket = bucket
        self._url_expires_in = url_expires_in
        self._client = None

    async def put_image(self, key: str, content: bytes, content_type: str) -> StoredImage:
        url = await asyncio.to_thread(self._put_and_sign, key, content, content_type)
        return StoredImage(
            key=key,
            url=url,
            url_expires_in=self._url_expires_in,
            bucket=self._bucket,
            content_type=content_type,
            size_bytes=len(content),
        )

    def _put_and_sign(self, key: str, content: bytes, content_type: str) -> str:
        client = self._client or s3_client()
        self._client = client
        try:
            client.put_object(
                Bucket=self._bucket, Key=key, Body=content, ContentType=content_type
            )
            return client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=self._url_expires_in,
            )
        except (BotoCoreError, ClientError) as e:
            # 자격 증명·버킷 권한·네트워크 실패 — 원본 메시지에 계정 정보가 섞일 수 있어 감춘다.
            raise ImageStorageUnavailableError(
                f"이미지 저장소에 접근할 수 없습니다(bucket={self._bucket})."
            ) from e
