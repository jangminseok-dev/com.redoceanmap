from market.domain.services.key_money import default_key_money, industry_group_for
from market.domain.value_objects.finance_vo import KeyMoneyBenchmark, Source


def test_서울시_업종_코드를_권리금_업종_대분류로_옮긴다():
    assert industry_group_for("CS100010") == "숙박 및 음식점업"   # 커피-음료
    assert industry_group_for("CS200034") == "숙박 및 음식점업"   # 여관
    assert industry_group_for("CS300002") == "도매 및 소매"        # 편의점
    assert industry_group_for("CS200033") == "부동산 및 임대업"    # 부동산중개업
    assert industry_group_for("CS200037") == "예술,스포츠 및, 여가 관련 서비스업"  # 노래방
    assert industry_group_for("CS200028") == "협회 및 단체,수리 및 기타 개인 서비스업"  # 미용실
    assert industry_group_for("CS200001") == "전체"               # 일반교습학원 — 대분류 표에 없음


def test_권리금_있는_점포가_절반_이상이면_중위수를_아니면_0을_가정한다():
    food = KeyMoneyBenchmark(2025, "숙박 및 음식점업", 79.1, 43_670_749)
    retail = KeyMoneyBenchmark(2025, "도매 및 소매", 31.6, 38_228_998)
    assert default_key_money(food).value == 43_670_749
    r = default_key_money(retail)
    assert r.value == 0 and r.source == Source.ASSUMED
    assert r.note == "권리금 0 가정(R-ONE 2025 서울 도매 및 소매은 권리금 있는 점포가 32%, 있으면 중위수 3,823만원)"
    assert default_key_money(None).note == "권리금 자료 없음 — 0 가정"
