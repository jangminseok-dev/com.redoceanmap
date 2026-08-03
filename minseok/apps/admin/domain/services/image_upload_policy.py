"""어드민 이미지 업로드 정책 — 순수 판정(외부 의존 없음).

무엇을 받아줄지(형식·크기)와 객체 키를 어떻게 짓는지는 **운영 정책**이지 S3의 세부가 아니다.
저장소를 S3에서 다른 것으로 바꿔도 이 규칙은 그대로 남는다.

형식은 **클라이언트가 선언한 content-type이 아니라 파일 앞머리(매직 바이트)로 판정한다.**
플러터 `MultipartFile`은 명시하지 않으면 `application/octet-stream`을 보내므로 선언을 믿으면
정상 이미지가 거부되고, 반대로 믿어주면 확장자만 바꾼 파일이 통과한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10MB — 모바일 촬영 원본 전제(PDF 20MB 선례보다 낮게)

# 판정된 content-type → 확장자. 화이트리스트 밖은 받지 않는다.
# SVG는 매직 바이트가 없고 스크립트를 품을 수 있어(브라우저에서 실행) 애초에 대상이 아니다.
ALLOWED_IMAGE_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

OBJECT_KEY_PREFIX = "admin/images"


@dataclass(frozen=True)
class ImageVerdict:
    """정책 판정 결과 — 실제 형식과 거절 사유(받아들일 수 있으면 reason=None)."""

    content_type: str | None
    reason: str | None


def _sniff(content: bytes) -> str | None:
    """파일 앞머리로 실제 형식을 판정한다. 화이트리스트 밖이면 None."""
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"GIF87a") or content.startswith(b"GIF89a"):
        return "image/gif"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def inspect(content: bytes) -> ImageVerdict:
    """업로드 바이트를 크기 → 형식 순으로 판정한다."""
    if not content:
        return ImageVerdict(content_type=None, reason="빈 파일입니다.")
    if len(content) > MAX_IMAGE_BYTES:
        return ImageVerdict(
            content_type=None,
            reason=f"이미지가 너무 큽니다(최대 {MAX_IMAGE_BYTES // (1024 * 1024)}MB).",
        )
    sniffed = _sniff(content)
    if sniffed is None:
        allowed = ", ".join(sorted(ALLOWED_IMAGE_TYPES))
        return ImageVerdict(
            content_type=None, reason=f"이미지 파일이 아닙니다(허용: {allowed})."
        )
    return ImageVerdict(content_type=sniffed, reason=None)


def build_object_key(content_type: str, unique_id: str, uploaded_at: datetime) -> str:
    """`admin/images/2026/08/<uuid>.jpg` — 연/월로 나눠 수명 정책·조회 범위를 좁힌다.

    원본 파일명은 키에 쓰지 않는다(경로 탈출·한글/공백 인코딩 문제를 원천 차단).
    확장자는 판정된 형식에서 뽑는다 — 파일명 확장자는 위조된다.
    """
    return f"{OBJECT_KEY_PREFIX}/{uploaded_at:%Y/%m}/{unique_id}{ALLOWED_IMAGE_TYPES[content_type]}"
