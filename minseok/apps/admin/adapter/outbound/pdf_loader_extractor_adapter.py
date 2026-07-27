"""neo4j-graphrag의 PdfLoader로 PDF 텍스트 레이어를 추출하는 어댑터.

`PdfLoader.run(filepath=...)`은 코루틴이지만 내부 pypdf 파싱은 동기 CPU 작업이라
그대로 await하면 이벤트 루프를 막는다. 그래서 정적 `load_file(file, fs)`을
`asyncio.to_thread`로 감싼다(백엔드 async 규칙: CPU-bound는 스레드로 분리).

PdfLoader는 파일 경로 + fsspec 파일시스템을 받으므로, 업로드 바이트는 임시 파일로
내려놓고 추출 직후 삭제한다 — PDF 원본은 어디에도 보관하지 않는다.
"""
from __future__ import annotations

import asyncio
import tempfile

import fsspec
from neo4j_graphrag.exceptions import PdfLoaderError
from neo4j_graphrag.experimental.components.data_loader import PdfLoader

from admin.app.exceptions import PdfExtractionError
from admin.app.ports.output.pdf_text_extractor_port import PdfTextExtractorPort


class PdfLoaderExtractorAdapter(PdfTextExtractorPort):
    """PdfTextExtractorPort의 neo4j-graphrag 구현."""

    def __init__(self) -> None:
        self._fs = fsspec.filesystem("file")

    async def extract(self, filename: str, content: bytes) -> str:
        return await asyncio.to_thread(self._extract_sync, filename, content)

    def _extract_sync(self, filename: str, content: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            tmp.write(content)
            tmp.flush()
            try:
                return PdfLoader.load_file(tmp.name, fs=self._fs)
            except PdfLoaderError as e:
                raise PdfExtractionError(f"PDF를 읽을 수 없습니다: {filename}") from e
