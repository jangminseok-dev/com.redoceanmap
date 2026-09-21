"""리포트 표기 규칙 — 한 줄에 한 사실, 값은 굵게, 보조 설명은 기울임, 전문 기호는 말로(2026-09-21 가독성 실측)."""
from chat.domain.services import compare as cs
from chat.domain.services.answer_guard import strip_area_codes
from chat.domain.services.report_format import bold_value, plain, predictiveness_word, section, split_note, trend_facts

TREND = ("- 분기 추이: 20251 매출 137.9억(QoQ -16.0%) 유동 100.2만(QoQ -4.8%) / 20252 매출 187.1억(QoQ +35.6%) 유동 105.4만(QoQ +5.2%)"
         " / 20253 매출 145.5억(QoQ -22.2%) 유동 100.2만(QoQ -4.9%)\n")


def test_첫_값만_굵게_하고_기간_표시는_값으로_보지_않는다():
    assert bold_value("점포당 월평균 981만원") == "점포당 월평균 **981만원**"
    assert bold_value("직장인구 4,421명이 상주인구의 2.0배") == "직장인구 **4,421명**이 상주인구의 2.0배"
    assert bold_value("최근 5일 거래량 20일 평균의 0.7배(평소보다 적음)") == "최근 5일 거래량 20일 평균의 **0.7배**(평소보다 적음)"
    assert bold_value("서울 1,064곳 중 **281위**") == "서울 1,064곳 중 **281위**"   # 호출부가 정한 굵게는 그대로


def test_끝에_붙은_산식_괄호는_보조_설명_줄로_뺀다():
    assert split_note("일평균 12,428명 (분기 총 1,130,942명 ÷ 91일)") == ["일평균 12,428명", "_분기 총 1,130,942명 ÷ 91일_"]
    assert split_note("유동인구 최다 연령 20대") == ["유동인구 최다 연령 20대"]


def test_섹션은_제목과_한_사실씩의_하위_목록이고_빈_섹션은_내지_않는다():
    assert section("수요", ["일평균 12,428명", "_분기 총 ÷ 91일_", plain("기사 — 3곳 신규 출점(09/13)")]) == [
        "- **수요**", "  - 일평균 **12,428명**", "  - _분기 총 ÷ 91일_", "  - 기사 — 3곳 신규 출점(09/13)"]
    assert section("재무", []) == [] and section("재무", [""]) == []


def test_예측력은_기호가_아니라_말로():
    assert [predictiveness_word(r) for r in (0.45, 0.30, 0.29, 0.15, -0.41, None)] == [
        "예측력 강함", "예측력 보통", "예측력 보통", "예측력 약함", "예측력 강함", ""]


def test_분기_추이는_최근_분기와_최고_최저로_줄인다():
    facts = trend_facts(TREND)
    assert facts == [
        "2025년 3분기 매출 **145.5억** — 전 분기 대비 **-22.2%**",
        "최근 3분기 최고 187.1억(2025년 2분기) · 최저 137.9억(2025년 1분기)",
        "2025년 3분기 유동인구 **100.2만명** — 전 분기 대비 **-4.9%**",
    ]
    assert all("QoQ" not in f and len(f) < 60 for f in facts)   # 원문은 분기마다 나열해 300자를 넘었다
    # 전 분기 값이 없는 첫 분기("QoQ -")와 형식을 못 읽는 입력은 열화 동작
    assert trend_facts("- 분기 추이: 20244 매출 3.2억(QoQ -) 유동 123.0만(QoQ -)\n") == ["2024년 4분기 매출 **3.2억**", "2024년 4분기 유동인구 **123.0만명**"]
    assert trend_facts("분기 추이: 20251 매출 증가(QoQ 미상)") == ["2025년 1분기 매출 증가(전 분기 대비 미상)"]


def test_상권_코드_괄호는_어떤_꼴로_새도_지운다():
    assert strip_area_codes("성수동카페거리(3110131)를 보세요") == "성수동카페거리를 보세요"
    assert strip_area_codes("성수동카페거리(trdar_code: 3110131)를 우선 검토") == "성수동카페거리를 우선 검토"   # 2026-09-21 실답변
    assert strip_area_codes("월 981만원(서울 상위 26%)") == "월 981만원(서울 상위 26%)"   # 다른 괄호는 그대로


def test_지표별_비교는_표이고_값이_없는_지표는_표_밖_한_줄로_모은다():
    a = cs.AreaCompareItem(1, "강남역", "", {}, 1655.0, 2.6, 81688.0, 109.0, False, 53.5, "보통")
    b = cs.AreaCompareItem(2, "홍대입구역(홍대)", "", {}, 196.0, 1.7, 45429.0, 85.0, False, 34.3, "주의")
    v = cs.area_verdict([a, b])
    blocks = cs._axis_table("**참고 지표별 비교**", ["강남역", "홍대입구역(홍대)"], v.results)
    assert blocks[0].split("\n")[1:3] == ["| 지표 | 강남역 | 홍대입구역(홍대) |", "|---|---|---|"]
    assert "| 점포당 월매출 | ★ 1,655만원 | 196만원 |" in blocks[0]
    assert "| 최근 1년 폐업률 | 2.6% | ★ 1.7% |" in blocks[0]
    assert "값 없음" not in blocks[0] and "비교 안 함" not in blocks[0]
    assert blocks[1].startswith("_값이 없어 비교하지 않은 지표: ") and "공실률" in blocks[1]
