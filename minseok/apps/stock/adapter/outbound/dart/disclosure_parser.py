"""DART 공시서류원본파일(XML) 파서 — 문서 → 청킹 입력(DocElement 목록).

2026-08-23 삼성전자 사업보고서(20260310002820) 실측으로 확정한 구조:
- ZIP 안 XML(UTF-8). **완전한 well-formed가 아니다** — 본문에 이스케이프 안 된
  `&`(R&D)와 장식용 `<`(`< TV 시장점유율 추이 >`)가 실재해 전처리로 살린다.
- 계층: BODY > SECTION-1(> SECTION-2 > SECTION-3), 각 섹션의 첫 TITLE이 제목.
- 표: TABLE-GROUP > TABLE > (COLGROUP·THEAD·TBODY) > TR > TD/TH/TU/TE.
  표지 메타 표(ACLASS="EXTRACTION")는 본문이 아니라 제외한다.
- 각주: 전용 태그가 없다 — **대부분 표 안의 행**('주)'로 시작하는 셀, 실측 640건)이고
  표 직후 '주)' P 문단은 드물다. 둘 다 각주로 승계한다.
- 캡션: 전용 태그가 없다 — 표 직전의 짧은 P(제목 꼴)를 캡션으로 승계한다.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from stock.domain.services.disclosure_chunker import DocElement, TableBlock

# 표 직전 문단을 캡션으로 볼 길이 상한 — 제목 꼴("< TV 시장점유율 추이 >")은 짧다
CAPTION_MAX = 60
# 각주 시작 꼴 2종 — "※ …"(삼성전자 실측 스타일)와 "주)"·"주1)"(타 보고서 통용).
# ⚠ 괄호로 시작하는 "(주)…"는 주식회사 상호라 각주가 아니다(실측 오분류 버그 — 계열사
# 목록 행 801개가 각주로 흡수됐었다). "(단위 : 원, 주)"의 '주'도 주식 수 단위일 뿐이다.
_FOOTNOTE_HEAD = re.compile(r"^(?:※|주\d{0,2}\s*\))")
_CELL_TAGS = ("TD", "TH", "TU", "TE")


# 실제 태그로 살릴 `<`의 전부 — 태그명(영문+하이픈) + 따옴표 값 속성들 + `>`. 그 밖의
# `<영문 …>`(예: "<ACI 세미나>", SK하이닉스 2026-08-24 실측)은 장식 텍스트라 이스케이프한다
# — "`<` 뒤 비영문자만 이스케이프" 1차 규칙이 놓치던 꼴.
_TAG_RE = re.compile(
    r"</?[A-Za-z][A-Za-z0-9:._-]*"
    r"(?:\s+[A-Za-z0-9:._-]+\s*=\s*(?:\"[^\"]*\"|'[^']*'))*"
    r"\s*/?>"
    r"|<[!?]"
)


def _sanitize(xml_text: str) -> str:
    """DART 원문의 비정형 토큰 2종을 살린다 — 실측 근거는 모듈 docstring."""
    fixed = re.sub(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)", "&amp;", xml_text)
    return re.sub(r"<", lambda m: "<" if _TAG_RE.match(m.string, m.start()) else "&lt;", fixed)


def _text_of(el: ET.Element) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def _parse_table(table: ET.Element) -> TableBlock | None:
    rows: list[tuple[str, ...]] = []
    footnotes: list[str] = []
    header: tuple[str, ...] = ()
    for tr in table.iter("TR"):
        cells = tuple(_text_of(c) for c in tr if c.tag in _CELL_TAGS)
        filled = [c for c in cells if c]
        if not filled:
            continue
        # 첫 TH 행을 헤더로 — 이후 TH 행(중첩 헤더)은 데이터로 두지 않고 버린다(페어링 오염 방지)
        if not header and any(c.tag == "TH" for c in tr):
            header = cells
            continue
        # 각주는 대부분 표 안의 행이다 — 첫 값 셀이 '주)' 꼴이면 데이터가 아니라 각주로 승계
        if _FOOTNOTE_HEAD.match(filled[0]):
            footnotes.append(" ".join(filled))
            continue
        rows.append(cells)
    if not rows and not header and not footnotes:
        return None
    return TableBlock(caption="", header=header, rows=tuple(rows), footnotes=tuple(footnotes))


def parse_document(xml_text: str) -> list[DocElement]:
    sanitized = _sanitize(xml_text)
    try:
        root = ET.fromstring(sanitized)
    except ET.ParseError:
        # 전처리로 못 살리는 깨진 원문이 실재한다(2026-08-24 실측 — NAVER `ENG=""…"` 깨진
        # 속성, POSCO 본문 장식 태그). lxml recover로 복구 파싱한다 — 오류 인접 텍스트
        # 일부 유실 감수. 정상 문서는 표준 ET 경로 유지.
        from lxml import etree

        root = etree.fromstring(
            sanitized.encode("utf-8"),
            parser=etree.XMLParser(recover=True, huge_tree=True),
        )
    body = root.find("BODY")
    if body is None:
        return []
    raw: list[tuple[str, str, object]] = []  # (section_path, kind, payload) — 문서 순서

    def walk(el: ET.Element, path: list[str]) -> None:
        for child in el:
            tag = child.tag
            if not isinstance(tag, str):
                continue  # lxml recover 경로의 주석 노드 — tag가 문자열이 아니다
            if tag == "TITLE":
                continue  # 섹션 진입 시 이미 소비
            if tag.startswith("SECTION-"):
                title_el = child.find("TITLE")
                title = _text_of(title_el) if title_el is not None else ""
                walk(child, path + ([title] if title else []))
            elif tag == "TABLE":
                if child.get("ACLASS") == "EXTRACTION":
                    continue  # 표지 메타 표 — 본문 아님
                block = _parse_table(child)
                if block is not None:
                    raw.append((" > ".join(path), "table", block))
            elif tag == "P":
                text = _text_of(child)
                if text:
                    raw.append((" > ".join(path), "text", text))
            else:
                walk(child, path)  # TABLE-GROUP·COVER 등 컨테이너 관통

    walk(body, [])

    # 인접성 후처리 — 직전 짧은 문단을 캡션으로 승계, 직후 '주)' 문단을 각주로 부착
    elements: list[DocElement] = []
    i = 0
    while i < len(raw):
        path, kind, payload = raw[i]
        if kind == "text":
            text = str(payload)
            is_caption = (
                len(text) <= CAPTION_MAX
                and i + 1 < len(raw) and raw[i + 1][1] == "table"
                and not _FOOTNOTE_HEAD.match(text)
            )
            if not is_caption:
                elements.append(DocElement(section_path=path, kind="text", text=text))
            i += 1
            continue
        table: TableBlock = payload  # type: ignore[assignment]
        # 각주만 남은 표(※ 한 줄짜리 안내 표 — DART가 데이터 표 '다음 표'로 각주를 싣는
        # 실측 패턴, 103건) → 직전 데이터 표에 각주로 승계, 붙일 표가 없으면 본문으로
        if not table.rows and not table.header:
            note = " ".join(table.footnotes)
            last = elements[-1] if elements else None
            if last is not None and last.table is not None and last.section_path == path:
                elements[-1] = DocElement(
                    section_path=last.section_path, kind="table",
                    table=TableBlock(
                        caption=last.table.caption, header=last.table.header,
                        rows=last.table.rows,
                        footnotes=last.table.footnotes + table.footnotes,
                    ),
                )
            elif note:
                elements.append(DocElement(section_path=path, kind="text", text=note))
            i += 1
            continue
        caption = ""
        if i > 0 and raw[i - 1][1] == "text":
            prev = str(raw[i - 1][2])
            if len(prev) <= CAPTION_MAX and not _FOOTNOTE_HEAD.match(prev):
                caption = prev
        footnotes = list(table.footnotes)  # 표 안의 각주 행 + 직후 각주 문단(P) 승계
        j = i + 1
        while j < len(raw) and raw[j][1] == "text" and _FOOTNOTE_HEAD.match(str(raw[j][2])):
            footnotes.append(str(raw[j][2]))
            j += 1
        elements.append(DocElement(
            section_path=path, kind="table",
            table=TableBlock(
                caption=caption, header=table.header,
                rows=table.rows, footnotes=tuple(footnotes),
            ),
        ))
        i = j
    return elements
