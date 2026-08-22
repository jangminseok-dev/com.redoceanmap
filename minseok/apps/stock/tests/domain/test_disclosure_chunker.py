"""disclosure_chunker 테스트 — 전략 3종의 규칙과 결정론을 고정한다."""
from __future__ import annotations

from stock.domain.services.disclosure_chunker import (
    FIXED_OVERLAP,
    FIXED_SIZE,
    Chunk,
    DocElement,
    TableBlock,
    chunk_by_section,
    chunk_fixed,
    chunk_table_aware,
)

_TABLE = TableBlock(
    caption="사업부문별 매출",
    header=("부문", "매출액", "비중"),
    rows=(
        ("반도체", "79,000,000", "45%"),
        ("디스플레이", "30,000,000", "17%"),
        ("합계", "175,000,000"),  # rowspan 등으로 셀 수가 어긋난 행
        ("", "", ""),             # 빈 행 — 버려야 한다
    ),
    footnotes=("주) 단위: 백만원",),
)

_ELEMENTS = [
    DocElement(section_path="I. 회사의 개요", kind="text", text="가" * 100),
    DocElement(section_path="II. 사업의 내용", kind="text", text="나" * 100),
    DocElement(section_path="II. 사업의 내용", kind="table", table=_TABLE),
    DocElement(section_path="II. 사업의 내용", kind="text", text="다" * 100),
]


def test_고정_분할은_오버랩을_두고_전체를_덮는다():
    long_doc = [DocElement(section_path="S", kind="text", text="가" * 1200)]
    chunks = chunk_fixed(long_doc)
    assert all(len(c.content) <= FIXED_SIZE for c in chunks)
    # 연속 청크는 앞 청크 꼬리(오버랩)를 공유한다
    step = FIXED_SIZE - FIXED_OVERLAP
    assert chunks[1].content[:FIXED_OVERLAP] == chunks[0].content[step:step + FIXED_OVERLAP]
    # 손실 없음 — 오버랩 제거 후 이어붙이면 원문이 복원된다
    rebuilt = chunks[0].content + "".join(c.content[FIXED_OVERLAP:] for c in chunks[1:])
    assert rebuilt == "가" * 1200


def test_고정_분할은_표를_선형화해_구조를_버린다():  # 대조군의 정의
    chunks = chunk_fixed(_ELEMENTS)
    joined = "\n".join(c.content for c in chunks)
    assert "반도체 | 79,000,000 | 45%" in joined      # 행이 평문으로 존재
    assert all(c.kind == "text" for c in chunks)      # 표 청크 없음


def test_섹션_분할은_섹션마다_한_청크_상한_초과면_재분할():
    chunks = chunk_by_section(_ELEMENTS)
    assert [c.section_path for c in chunks] == ["I. 회사의 개요", "II. 사업의 내용"]
    long_section = [DocElement(section_path="S", kind="text", text="가" * 5000)]
    assert len(chunk_by_section(long_section)) > 1    # SECTION_MAX 초과 → 고정 재분할


def test_표_인지는_행_단위_헤더_페어링과_각주_인라인():
    chunks = chunk_table_aware(_ELEMENTS)
    tables = [c for c in chunks if c.kind == "table"]
    assert len(tables) == 3  # 빈 행 제외, 데이터 3행
    first = tables[0].content
    assert first.startswith("[II. 사업의 내용] 사업부문별 매출")  # 섹션·캡션 승계
    assert "부문=반도체 | 매출액=79,000,000 | 비중=45%" in first  # 헤더=값 페어링
    assert "주석: 주) 단위: 백만원" in first                      # 각주 인라인
    # 셀 수 불일치 행은 페어링 대신 단순 나열 폴백
    assert "합계 | 175,000,000" in tables[2].content and "=" not in tables[2].content.splitlines()[1]
    # 텍스트는 섹션 규칙 유지 — 같은 섹션의 표 앞뒤 텍스트가 각각 병합된다
    texts = [c for c in chunks if c.kind == "text"]
    assert {c.section_path for c in texts} == {"I. 회사의 개요", "II. 사업의 내용"}


def test_결정론_같은_입력이면_세_전략_모두_같은_출력():
    for fn in (chunk_fixed, chunk_by_section, chunk_table_aware):
        assert fn(list(_ELEMENTS)) == fn(list(_ELEMENTS))
        assert all(isinstance(c, Chunk) for c in fn(list(_ELEMENTS)))
