"""비교·단일 상권 답의 깊이(2026-09-17 실사용 — "정보량과 깊이감이 너무 없다")."""
from chat.domain.services import compare as cs


def _item(name, **kw):
    base = dict(code=hash(name) % 10**6, name=name, district="성동구",
                texts={"revenue_text": "점포당 월평균 1,000만원", "foot_text": "일평균 10,000명", "store_count_text": "50개 점포 영업 중"},
                sales_per_store=1000.0, closure_rate=2.0, foot_daily=10000.0, operating_months=100.0, small_sample=False,
                score_total=55.0, grade="보통")
    base.update(kw)
    return cs.AreaCompareItem(**base)


def test_상권별_특장점은_곳마다_강점과_약점을_수치와_함께_쓴다():
    items = [_item("A", sales_per_store=2000.0, closure_rate=4.0), _item("B", foot_daily=30000.0), _item("C", closure_rate=1.0)]
    v = cs.area_verdict(items)
    block = cs.strengths_block(items, v.results)
    rows = block.split("\n")
    start = rows.index("- **A** ('보통' 55.0점)")
    a_facts = [r for r in rows[start + 1:rows.index("- **B** ('보통' 55.0점)")]]
    # 한 줄에 한 사실(2026-09-21) — 강점은 ○, 약점은 ✕, 값은 굵게
    assert "  - ○ 점포당 월매출 **2,000만원**(3곳 중 1위)" in a_facts
    assert "  - ✕ 최근 1년 폐업률 **4.0%**(3곳 중 최고)" in a_facts
    assert "  - ○ 일평균 유동인구 **30,000명**(3곳 중 1위)" in rows
    assert all(len(r) < 80 for r in rows)  # 예전엔 곳마다 '강점 — … / 약점 — … / 성격 — …' 한 줄이었다


def test_업종_매출이_없는_상권은_등급이_높아도_1순위에서_뺀다():
    items = [_item("시장", grade="양호", score_total=78.0, has_industry_sales=False), _item("역", grade="보통", score_total=51.0),
             _item("거리", grade="주의", score_total=40.0)]
    v = cs.area_verdict(items)
    assert v.first == "역" and "이 업종 매출 기록 없음(1순위 판정 제외): 시장" in v.line


def test_특장점_후속은_전체_표를_반복하지_않고_곳마다_풀어_쓴다():
    items = [_item("A", insights=("오피스 상권입니다.",), trend="분기 추이: 20251 매출 1.0억", finance={"rent": 300, "gap": 1200}),
             _item("B", grade="양호", score_total=70.0)]
    v = cs.area_verdict(items)
    text = cs.render_area_compare(items, v, service_name="커피-음료", quarter_label="2026년 2분기", brief=False,
                                  missing_notes=[], focus="strengths")
    assert "**상권별 특장점**" in text and "**전체 지표**" not in text
    assert "- **추이**\n  - 2025년 1분기 매출 **1.0억**" in text   # 형식을 못 읽는 추이는 기호만 말로 바꿔 그대로
    assert "- **재무**\n  - 월세(추정) **300만원**" in text and "  - 부족 자금 **1,200만원**" in text


def test_단일_상권_리포트는_판단_순서대로_수치와_서울_기준을_붙인다():
    item = _item("성수동카페거리", rank_sales=(101, 1064), rank_closure=(620, 1508), insights=("오피스 상권입니다.",),
                 components=(("closure_stability", "폐업 안정성", 70.0, 1.3, 2.5),),
                 backtest={"n": 3158, "closure": 2.25, "closure_n": 3158})
    text = cs.render_area_report(item, service_name="커피-음료", quarter_label="2026년 2분기", missing_notes=["임대료 — 자기자본을 알려주세요"],
                                 predictiveness={"closure_stability": (0.296, 0.84, 24669)})
    order = [text.index(h) for h in ("**수익성**", "**안정성**", "**수요**", "**고객·배후 성격**", "**경쟁**")]
    assert order == sorted(order)
    assert "  - 서울 1,064곳 중 **101위**" in text and "서울 낮은 순 620위/1,508곳" in text
    assert "  - 폐업 안정성 **70점** — 4분기 폐업률 1.3% · 서울 중앙 4분기 폐업률 2.5% · 예측력 보통" in text
    assert "ρ" not in text and "QoQ" not in text   # 전문 기호는 말로
    assert "  - 같은 '보통' 등급의 다음 1년 폐업률 실측 **2.25%**\n  - _백테스트 3,158건 평균_" in text
    detail = text.split("**세부 근거**\n", 1)[1].split("\n\n", 1)[0]
    assert "\n\n" not in detail and max(len(r) for r in detail.split("\n")) < 90   # 접히는 한 단락 · 한 줄에 한 사실
    assert "**이 리포트에 못 쓴 데이터**" in text


def test_한눈에_판단은_서울_기준_좋은_편_보통_나쁜_편을_가른다():
    item = _item("성수", rank_sales=(101, 1064), rank_closure=(1200, 1508), grade="양호", score_total=66.5,
                 fitness={"total": 72, "components": (("수요 정합", 0.97, 0.3), ("경쟁 여유", 0.27, 0.2)), "diagnoses": ()},
                 finance={"attainment": 0.9, "gap": 3000})
    lines = cs.glance_lines(item)
    assert lines[0].startswith("**한눈에**")
    assert "- ○ 수익성 — 점포당 매출 서울 상위 9%" in lines
    assert "- ✕ 안정성 — 1년 폐업률 2.0%, 서울에서 낮은 쪽 상위 80%" in lines
    assert "- ○ 수요 궁합 — 이 업종 고객층과 상권 유동인구 정합 97점" in lines
    assert "- ✕ 경쟁 — 유동인구 대비 같은 업종 밀도 여유 27점" in lines
    assert "- ✕ 재무 — 지금 점포당 매출이면 손익분기 90% 달성, 부족 자금 3,000만원" in lines


def test_리포트는_한눈에와_접히는_세부_근거로_나뉜다():
    item = _item("성수", rank_sales=(101, 1064))
    text = cs.render_area_report(item, service_name="커피-음료", quarter_label="2026년 2분기", missing_notes=[])
    paragraphs = text.split("\n\n")
    assert paragraphs[0].startswith(cs.REPORT_HEADING) and "**한눈에**" in paragraphs[0]
    assert paragraphs[1].startswith(cs.DETAIL_HEADING) and "- **수익성**" in paragraphs[1]


def test_모든_곳에_같은_꼴의_진단은_공통_한_줄로_모은다():
    diag = lambda age: {"total": 60, "components": (), "diagnoses": (("bad", f"커피-음료 매출의 29%는 30대에서 나오는데, 이 상권 유동인구는 {age}가 가장 많습니다."),)}
    items = [_item("A", fitness=diag("20대(27%)")), _item("B", fitness=diag("60대 이상(23%)"))]
    block = cs.strengths_block(items, cs.area_verdict(items).results)
    assert block.count("30대에서 나오는") == 1
    assert "- 공통 주의 — 커피-음료 매출의 29%는 30대에서 나오는는데" not in block
    assert "공통 주의 — 커피-음료 매출의 29%는 30대에서 나오는데, 비교한 2곳 모두" in block


def test_여러_상권_등급_고지는_한_문장이다():
    from chat.domain.services.answer_guard import grade_caution_notice_group
    text = grade_caution_notice_group([("홍대", "주의", 38.8), ("길음역 8번", "주의", 34.3)])
    assert text.count("※") == 1 and "홍대(38.8점 '주의')·길음역 8번(34.3점 '주의')" in text and "등급으로" in text


def test_적합도가_있어도_리포트_머리와_한눈에가_유지된다():
    # 2026-09-17 실데이터 재생: 적합도 구간의 지역 변수가 리포트 머리를 덮어써 "6 / 9 / 점"이 찍혔다
    item = _item("성수", rank_sales=(101, 1064),
                 fitness={"total": 69, "components": (("수요 정합", 0.95, 0.3),), "diagnoses": ()})
    text = cs.render_area_report(item, service_name="커피-음료", quarter_label="2026년 2분기", missing_notes=[])
    first = text.split("\n\n")[0]
    assert first.startswith(f"{cs.REPORT_HEADING}성수**") and "**한눈에**" in first
    assert "\n6\n" not in text
