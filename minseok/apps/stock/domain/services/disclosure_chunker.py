"""공시 청킹 전략 3종(R3) — 표·각주가 있는 실제 문서에서 청킹이 검색 품질을 바꾸는지 잰다.

순수 함수(표준 라이브러리만). 입력은 파서(adapter/outbound/dart/disclosure_parser.py)가
만든 문서 요소 목록이고, 출력은 전략별 청크 목록이다 — 같은 입력이면 항상 같은 출력.

- (a) chunk_fixed        : 고정 512자/오버랩 64자 (대조군 — 구조 무시).
  로드맵의 "고정 토큰 512"를 문자 단위로 근사한다(전용 토크나이저 미보유 — 한계 명시).
- (b) chunk_by_section   : 섹션 헤딩 단위 병합. 상한 초과 섹션은 (a) 규칙으로 재분할.
- (c) chunk_table_aware  : 텍스트는 (b)와 동일하되 표는 **행 단위** 청크로 —
  섹션 경로·표 캡션·헤더를 각 행에 승계(헤더=값 페어링)하고 각주는 행 청크에 인라인.
  "표를 봐야만 답하는 질의"에서 (a) 대비 recall@5 +0.10이 채택 게이트(ROADMAP R3).
"""
from __future__ import annotations

from dataclasses import dataclass

FIXED_SIZE = 512     # (a) 청크 폭 — 문자 단위 근사
FIXED_OVERLAP = 64
SECTION_MAX = 2000   # (b)(c) 섹션 병합 상한 — 초과 시 고정 분할로 재분할(임베딩 입력 예산)
FOOTNOTE_INLINE_MAX = 300  # (c) 행 청크에 인라인할 각주 총량 상한 — 행마다 붙어 부풀지 않게
ROW_CHUNK_MAX = 1000  # (c) 행 청크 상한 — 거대 병합 셀(실측 최대 2.3만 자)이 임베딩 예산을 넘지 않게


@dataclass(frozen=True)
class TableBlock:
    """표 1개 — 파서가 캡션(직전 짧은 문단)·헤더 행·각주(직후 '주)' 문단)를 붙여 준다."""

    caption: str
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    footnotes: tuple[str, ...] = ()


@dataclass(frozen=True)
class DocElement:
    """문서 요소 1개 — 문서 순서 그대로."""

    section_path: str          # 예: "II. 사업의 내용 > 4. 매출 및 수주상황"
    kind: str                  # text | table
    text: str = ""
    table: TableBlock | None = None


@dataclass(frozen=True)
class Chunk:
    section_path: str
    kind: str                  # text | table
    content: str


def _linearize_table(t: TableBlock) -> str:
    """표 → 평문 (a)(b)용 — 구조를 버리고 셀을 이어붙인다(대조군의 정의)."""
    lines = []
    if t.caption:
        lines.append(t.caption)
    if t.header:
        lines.append(" | ".join(t.header))
    lines.extend(" | ".join(row) for row in t.rows)
    lines.extend(t.footnotes)
    return "\n".join(lines)


def _element_text(e: DocElement) -> str:
    return _linearize_table(e.table) if e.table is not None else e.text


def _fixed_split(text: str, section_path: str, size: int = FIXED_SIZE,
                 overlap: int = FIXED_OVERLAP) -> list[Chunk]:
    step = size - overlap
    chunks = []
    for start in range(0, max(len(text), 1), step):
        piece = text[start:start + size].strip()
        if piece:
            chunks.append(Chunk(section_path=section_path, kind="text", content=piece))
        if start + size >= len(text):
            break
    return chunks


def chunk_fixed(elements: list[DocElement]) -> list[Chunk]:
    """(a) 대조군 — 문서 전체를 한 스트림으로 이어붙여 512/64 고정 분할.

    section_path는 청크 시작 위치가 속한 요소의 것을 기록한다(경계 청크는 앞 요소 귀속).
    """
    stream: list[tuple[int, str]] = []  # (누적 시작 오프셋, section_path)
    parts: list[str] = []
    offset = 0
    for e in elements:
        text = _element_text(e)
        if not text.strip():
            continue
        stream.append((offset, e.section_path))
        parts.append(text)
        offset += len(text) + 1  # 결합자 "\n"
    full = "\n".join(parts)

    def path_at(pos: int) -> str:
        current = ""
        for start, path in stream:
            if start > pos:
                break
            current = path
        return current

    step = FIXED_SIZE - FIXED_OVERLAP
    chunks = []
    for start in range(0, max(len(full), 1), step):
        piece = full[start:start + FIXED_SIZE].strip()
        if piece:
            chunks.append(Chunk(section_path=path_at(start), kind="text", content=piece))
        if start + FIXED_SIZE >= len(full):
            break
    return chunks


def _merge_sections(elements: list[DocElement]) -> list[Chunk]:
    """연속된 같은 섹션의 텍스트를 병합 — (b)의 본체이자 (c)의 텍스트 규칙."""
    chunks: list[Chunk] = []
    buffer: list[str] = []
    current_path: str | None = None

    def flush() -> None:
        if current_path is None or not buffer:
            return
        merged = "\n".join(buffer).strip()
        if not merged:
            return
        if len(merged) <= SECTION_MAX:
            chunks.append(Chunk(section_path=current_path, kind="text", content=merged))
        else:
            chunks.extend(_fixed_split(merged, current_path))

    for e in elements:
        if e.section_path != current_path:
            flush()
            buffer, current_path = [], e.section_path
        buffer.append(_element_text(e))
    flush()
    return chunks


def chunk_by_section(elements: list[DocElement]) -> list[Chunk]:
    """(b) 섹션 헤딩 분할 — 표는 선형화해 섹션 텍스트에 섞는다(표 인지는 (c)의 몫)."""
    return _merge_sections(elements)


def chunk_table_aware(elements: list[DocElement]) -> list[Chunk]:
    """(c) 표 인지 — 표는 행 단위 + 섹션·캡션·헤더 승계 + 각주 인라인, 텍스트는 (b)와 동일."""
    chunks: list[Chunk] = []
    text_buffer: list[DocElement] = []

    def flush_text() -> None:
        if text_buffer:
            chunks.extend(_merge_sections(text_buffer))
            text_buffer.clear()

    for e in elements:
        if e.table is None:
            text_buffer.append(e)
            continue
        flush_text()
        t = e.table
        prefix = f"[{e.section_path}]" if not t.caption else f"[{e.section_path}] {t.caption}"
        footnote = " ".join(t.footnotes).strip()[:FOOTNOTE_INLINE_MAX]
        for row in t.rows:
            if not any(cell.strip() for cell in row):
                continue
            if t.header and len(row) == len(t.header):
                body = " | ".join(f"{h}={v}" for h, v in zip(t.header, row))
            else:
                # rowspan/colspan으로 셀 수가 어긋난 행 — 페어링 대신 단순 나열 폴백
                body = " | ".join(cell for cell in row if cell.strip())
            content = f"{prefix}\n{body}"
            if footnote:
                content += f"\n주석: {footnote}"
            chunks.append(Chunk(
                section_path=e.section_path, kind="table", content=content[:ROW_CHUNK_MAX],
            ))
    flush_text()
    return chunks


STRATEGIES = {
    "a": chunk_fixed,
    "b": chunk_by_section,
    "c": chunk_table_aware,
}
