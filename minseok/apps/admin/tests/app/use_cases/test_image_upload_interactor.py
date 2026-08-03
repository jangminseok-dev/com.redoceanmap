import pytest

from admin.app.dtos.image_upload_dto import ImageUploadCommand, StoredImage
from admin.app.exceptions import ImageUploadRejectedError
from admin.app.use_cases.image_upload_interactor import ImageUploadInteractor
from admin.domain.services.image_upload_policy import MAX_IMAGE_BYTES

_PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32
_JPEG = b"\xff\xd8\xff\xe0" + b"0" * 32


class _StubStorage:
    def __init__(self):
        self.received = None

    async def put_image(self, key, content, content_type):
        self.received = dict(key=key, content=content, content_type=content_type)
        return StoredImage(
            key=key,
            url=f"https://example.invalid/{key}?sig=x",
            url_expires_in=900,
            bucket="test-bucket",
            content_type=content_type,
            size_bytes=len(content),
        )


class _StubAudit:
    def __init__(self):
        self.written = None

    async def write(self, actor_id, action, detail):
        self.written = (actor_id, action, detail)

    async def list_recent(self, limit):
        raise NotImplementedError


def _build(storage=None, audit=None):
    return ImageUploadInteractor(storage=storage or _StubStorage(), audit=audit or _StubAudit())


def _command(content=_PNG, **kwargs):
    return ImageUploadCommand(
        actor_id=kwargs.get("actor_id", 3),
        filename=kwargs.get("filename", "shop.png"),
        declared_content_type=kwargs.get("declared_content_type", "image/png"),
        content=content,
    )


async def test_업로드는_저장_후_감사를_남긴다():
    storage, audit = _StubStorage(), _StubAudit()

    result = await _build(storage=storage, audit=audit).upload(_command())

    assert storage.received["content"] == _PNG
    assert result.url.startswith("https://") and result.size_bytes == len(_PNG)
    actor_id, action, detail = audit.written
    assert (actor_id, action) == (3, "image.upload")
    assert f"key={result.key}" in detail and "file=shop.png" in detail


async def test_객체_키는_날짜_구간과_판정된_확장자로_짓는다():
    storage = _StubStorage()
    result = await _build(storage=storage).upload(_command(filename="../../etc/passwd"))

    assert result.key.startswith("admin/images/") and result.key.endswith(".png")
    assert ".." not in result.key and "passwd" not in result.key  # 파일명은 키에 섞이지 않는다


async def test_선언된_형식이_아니라_바이트로_판정한다():
    """플러터 MultipartFile 기본값(application/octet-stream)도 통과해야 한다."""
    storage = _StubStorage()
    result = await _build(storage=storage).upload(
        _command(content=_JPEG, filename="photo", declared_content_type="application/octet-stream")
    )

    assert storage.received["content_type"] == "image/jpeg" and result.key.endswith(".jpg")


async def test_이미지가_아니면_거부하고_저장하지_않는다():
    storage, audit = _StubStorage(), _StubAudit()
    interactor = _build(storage=storage, audit=audit)

    with pytest.raises(ImageUploadRejectedError):
        await interactor.upload(_command(content=b"%PDF-1.7 not an image", declared_content_type="image/png"))

    assert storage.received is None and audit.written is None


async def test_빈_파일과_한도_초과는_거부한다():
    with pytest.raises(ImageUploadRejectedError):
        await _build().upload(_command(content=b""))

    oversized = _PNG + b"0" * MAX_IMAGE_BYTES
    with pytest.raises(ImageUploadRejectedError):
        await _build().upload(_command(content=oversized))
