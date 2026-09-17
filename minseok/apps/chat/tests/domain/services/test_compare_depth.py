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
    a_line = next(line for line in block.split("\n") if line.startswith("- **A**"))
    assert "점포당 월매출 2,000만원(3곳 중 1위)" in a_line
    assert "약점 — 최근 1년 폐업률 4.0%(3곳 중 최고)" in a_line
    assert "일평균 유동인구 30,000명(3곳 중 1위)" in block


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
    assert "- 추이: 분기 추이: 2025년 1분기 매출 1.0억" in text
    assert "- 재무: 월세(추정) 300만원" in text and "부족 자금 1,200만원" in text


def test_단일_상권_리포트는_판단_순서대로_수치와_서울_기준을_붙인다():
    item = _item("성수동카페거리", rank_sales=(101, 1064), rank_closure=(620, 1508), insights=("오피스 상권입니다.",),
                 components=(("closure_stability", "폐업 안정성", 70.0, 1.3, 2.5),),
                 backtest={"n": 3158, "closure": 2.25, "closure_n": 3158})
    text = cs.render_area_report(item, service_name="커피-음료", quarter_label="2026년 2분기", missing_notes=["임대료 — 자기자본을 알려주세요"],
                                 predictiveness={"closure_stability": (0.296, 0.84, 24669)})
    order = [text.index(h) for h in ("**수익성**", "**안정성**", "**수요**", "**고객·배후 성격**", "**경쟁**")]
    assert order == sorted(order)
    assert "서울 1,064곳 중 101위" in text and "서울 낮은 순 620위/1,508곳" in text
    assert "폐업 안정성 70점(4분기 폐업률 1.3% / 서울 중앙 4분기 폐업률 2.5%, 예측력 ρ=+0.30)" in text
    assert "같은 '보통' 등급 상권의 다음 1년 폐업률 실측 평균 2.25%" in text
    assert "**이 리포트에 못 쓴 데이터**" in text
