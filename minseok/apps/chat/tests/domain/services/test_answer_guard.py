from chat.domain.services import answer_guard


def test_근거에_없는_숫자_문장은_걷어낸다():
    ctx = "[홍대입구역] 점포: 60개 점포 영업 중 | 분기 폐업률 2.5%(3개)\n유동인구: 일평균 15,503명"
    grounded = answer_guard.grounded_numbers(ctx)
    text = "홍대입구역은 37개의 네일숍이 경쟁합니다. 일평균 15,503명이 지나가고 폐업률은 2.5%입니다. 유의할 점: 폐업 [1] 참고."
    out = answer_guard.strip_ungrounded_numbers(text, grounded)
    assert "37개" not in out and "15,503명" in out and "2.5%" in out and "[1]" in out
    # 전부 걷히면 원문 유지(빈 답 방지)
    assert answer_guard.strip_ungrounded_numbers("개업 12곳, 폐업 45곳.", set()) == "개업 12곳, 폐업 45곳."


def test_등급_고지는_점수_이름을_붙인다():
    assert "상권 전체 건강 점수" in answer_guard.grade_caution_notice("성수역", "주의", 44.9)
