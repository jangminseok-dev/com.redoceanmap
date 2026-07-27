"""admin 앱 계약 예외 — 라우터가 HTTP 상태로 구분 매핑한다(chat app.exceptions 선례)."""


class GradeValidationError(ValueError):
    """등급 입력 검증 실패(탭 키·code 형식) — 400."""


class GradeProtectedError(ValueError):
    """보호 등급(admin) 삭제·개명 시도 — 409."""


class PdfExtractionError(ValueError):
    """PDF 파싱 실패(손상 파일·암호화 등) — 400."""


class PdfTextEmptyError(ValueError):
    """파싱은 됐으나 텍스트 레이어가 없음(스캔 이미지 PDF) — 400. OCR은 범위 밖."""


class PdfDocumentNotFoundError(ValueError):
    """요청한 PDF 문서 부재 — 404."""
