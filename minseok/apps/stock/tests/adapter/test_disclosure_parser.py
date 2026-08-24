"""disclosure_parser 테스트 — DART 원문의 실측 함정(비정형 토큰·캡션·각주)을 고정한다."""
from __future__ import annotations

from stock.adapter.outbound.dart.disclosure_parser import parse_document

# 2026-08-23 삼성전자 사업보고서 실측 구조의 축소판 — 비정형 &·< 포함
_XML = """<?xml version="1.0" encoding="utf-8"?>
<DOCUMENT>
<BODY>
<COVER>
<TABLE ACLASS="EXTRACTION"><TBODY><TR><TD>사업연도</TD><TD>2025</TD></TR></TBODY></TABLE>
</COVER>
<SECTION-1><TITLE>II. 사업의 내용</TITLE>
<P>당사는 R&D 역량을 바탕으로 성장했습니다.</P>
<SECTION-2><TITLE>4. 매출 및 수주상황</TITLE>
<P>< 사업부문별 매출 ></P>
<TABLE-GROUP>
<TABLE ACLASS="NORMAL">
<THEAD><TR><TH>부문</TH><TH>매출액</TH></TR></THEAD>
<TBODY>
<TR><TD>반도체</TD><TU>79,000,000</TU></TR>
<TR><TD>디스플레이</TD><TU>30,000,000</TU></TR>
<TR><TD></TD><TD></TD></TR>
<TR><TD>주1) 표 안의 각주 행입니다.</TD><TD></TD></TR>
</TBODY>
</TABLE>
</TABLE-GROUP>
<P>주) 단위: 백만원</P>
<P>주2) 연결 기준입니다.</P>
<P>상기 매출은 외부 감사를 거쳤습니다.</P>
</SECTION-2>
</SECTION-1>
</BODY>
</DOCUMENT>
"""


def test_비정형_토큰과_표지_메타를_흡수하고_구조를_뽑는다():
    elements = parse_document(_XML)
    kinds = [(e.section_path, e.kind) for e in elements]
    # 표지 EXTRACTION 표는 제외, 캡션 문단은 표에 흡수되어 별도 요소가 아니다
    assert kinds == [
        ("II. 사업의 내용", "text"),
        ("II. 사업의 내용 > 4. 매출 및 수주상황", "table"),
        ("II. 사업의 내용 > 4. 매출 및 수주상황", "text"),
    ]
    assert "R&D 역량" in elements[0].text  # bare & 전처리 생존


def test_영문으로_시작하는_장식_토큰도_본문으로_살린다():
    # SK하이닉스 실측(2026-08-24) — "<ACI 세미나>"는 태그 꼴이 아니라 장식 텍스트다
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        "<DOCUMENT><BODY><SECTION-1><TITLE>I. 회사의 개요</TITLE>"
        "<P>- 제11회 <ACI 세미나> 개최</P>"
        "</SECTION-1></BODY></DOCUMENT>"
    )
    elements = parse_document(xml)
    assert [e.kind for e in elements] == ["text"]
    assert "<ACI 세미나>" in elements[0].text


def test_표는_캡션_헤더_각주가_승계된다():
    table = parse_document(_XML)[1].table
    assert table.caption == "< 사업부문별 매출 >"      # bare < 전처리 생존
    assert table.header == ("부문", "매출액")
    assert table.rows == (("반도체", "79,000,000"), ("디스플레이", "30,000,000"))  # 빈 행 제외
    # 표 안의 각주 행(주 경로 — 실측 640건)이 먼저, 표 직후 '주)' 문단(보조)이 뒤에
    assert table.footnotes == (
        "주1) 표 안의 각주 행입니다.", "주) 단위: 백만원", "주2) 연결 기준입니다.",
    )


def test_각주_다음_일반_문단은_본문으로_남는다():
    elements = parse_document(_XML)
    assert elements[2].text == "상기 매출은 외부 감사를 거쳤습니다."
