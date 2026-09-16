import pytest

from chat.domain.services.amount_parser import (
    fmt_won,
    parse_budget_krw,
    parse_labeled_amounts,
    parse_won,
    solo_amount,
)


@pytest.mark.parametrize("text,won", [
    ("1억 2천으로 카페", 120_000_000), ("8천만원이면", 80_000_000), ("5000만원", 50_000_000),
    ("1.5억", 150_000_000), ("3,000만원", 30_000_000), ("5천", 50_000_000), ("2억", 200_000_000),
])
def test_금액_표기(text, won):
    assert parse_won(text) == won
    assert parse_budget_krw(text) == won or "5천" == text.strip() or "3,000" in text


def test_기존_예산_파서는_그대로다():
    assert parse_budget_krw("1억 2천으로 카페") == 120_000_000
    assert parse_budget_krw("예산은 얼마") is None


@pytest.mark.parametrize("text,expected", [
    ("자기자본 1억, 보증금 5천에 월세 300", {"equity": 100_000_000, "deposit": 50_000_000, "monthly_rent": 3_000_000}),
    ("내 돈 7천만원이고 월세는 250만원", {"equity": 70_000_000, "monthly_rent": 2_500_000}),
    ("임대료 180에 권리금 2천", {"monthly_rent": 1_800_000, "key_money": 20_000_000}),
    ("인테리어 3천만원 잡고 대출 5천 생각 중", {"startup_cost": 30_000_000, "desired_loan": 50_000_000}),
    ("20평 매장, 알바 2명", {"area_sqm": 66.1, "headcount": 2}),
    ("66㎡에 직원 1명", {"area_sqm": 66.0, "headcount": 1}),
    ("자본금 1.5억", {"equity": 150_000_000}),
    ("가진 돈 3억이야", {"equity": 300_000_000}),
    ("월세 300만 원", {"monthly_rent": 3_000_000}),
    ("보증금 1억 월세 500", {"deposit": 100_000_000, "monthly_rent": 5_000_000}),
    ("성수동 카페 어때?", {}),
    ("1억으로 치킨집", {}),  # 라벨 없는 단독 금액은 예산(기존 경로) — 라벨 파서는 비운다
])
def test_라벨_금액(text, expected):
    got = parse_labeled_amounts(text)
    assert {k: (round(v, 1) if isinstance(v, float) else v) for k, v in got.items()} == expected


def test_fmt_won():
    assert fmt_won(120_000_000) == "1억 2,000만원" and fmt_won(80_360_000) == "8,036만원"


@pytest.mark.parametrize("text,won", [
    ("성수동 카페 1억으로 월세 300이면?", 100_000_000),  # 라벨 금액과 공존해도 단독 금액을 살린다
    ("월세 300만원이면?", None),
    ("자기자본 1억", None),  # 라벨에 붙은 금액은 단독이 아니다
    ("1억으로 치킨집", 100_000_000),
])
def test_단독_금액(text, won):
    assert solo_amount(text) == won


def test_천원_소액은_천만원으로_읽지_않는다():
    assert parse_won("아메리카노 5천원") is None
    assert solo_amount("성수동 카페 아메리카노 5천원인데 월세 300이면 손익분기 얼마야?") is None
    assert parse_labeled_amounts("보증금 5천원") == {}
    assert parse_won("보증금 5천") == 50_000_000  # 관용 표기는 유지


@pytest.mark.parametrize("text,expected", [
    ("자기자본 1억 20평 월세 400", {"equity": 100_000_000, "area_sqm": 66.1, "monthly_rent": 4_000_000}),
    ("자기자본 1억 2명 고용", {"equity": 100_000_000, "headcount": 2}),
    ("자기자본 1억 2000만원", {"equity": 120_000_000}),
    ("자기자본 1억 2천", {"equity": 120_000_000}),
    ("자기자본 1억 2천만원", {"equity": 120_000_000}),
])
def test_억_뒤_단위_없는_숫자는_금액에_흡수하지_않는다(text, expected):
    got = parse_labeled_amounts(text)
    assert {k: (round(v, 1) if isinstance(v, float) else v) for k, v in got.items()} == expected


def test_예산_파서도_억_뒤_숫자를_흡수하지_않는다():
    assert parse_budget_krw("1억 20평 카페") == 100_000_000
    assert parse_budget_krw("1억 2000만원") == 120_000_000
    assert parse_budget_krw("1억 2천으로 카페") == 120_000_000
