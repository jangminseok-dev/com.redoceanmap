from datetime import datetime, timezone

from admin.domain.services.image_upload_policy import (
    MAX_IMAGE_BYTES,
    build_object_key,
    inspect,
)


def test_매직_바이트로_형식을_판정한다():
    assert inspect(b"\xff\xd8\xff\xe0" + b"0" * 16).content_type == "image/jpeg"
    assert inspect(b"\x89PNG\r\n\x1a\n" + b"0" * 16).content_type == "image/png"
    assert inspect(b"GIF89a" + b"0" * 16).content_type == "image/gif"
    assert inspect(b"RIFF" + b"0000" + b"WEBP" + b"0" * 16).content_type == "image/webp"


def test_이미지가_아니면_사유를_돌려준다():
    verdict = inspect(b"<svg xmlns='http://www.w3.org/2000/svg'/>")
    assert verdict.content_type is None and "이미지 파일이 아닙니다" in verdict.reason


def test_빈_파일과_한도_초과를_구분해서_거절한다():
    assert inspect(b"").reason == "빈 파일입니다."
    assert "너무 큽니다" in inspect(b"\x89PNG\r\n\x1a\n" + b"0" * MAX_IMAGE_BYTES).reason


def test_객체_키는_연월_구간과_확장자를_갖는다():
    key = build_object_key(
        content_type="image/jpeg",
        unique_id="abc123",
        uploaded_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
    )
    assert key == "admin/images/2026/08/abc123.jpg"
