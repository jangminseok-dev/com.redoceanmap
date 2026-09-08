import pytest

from market.domain.services.area_fitness import (
    cosine,
    evaluate,
)

# 20대에 몰린 업종 / 20대가 많은 거리 / 50대가 많은 거리
YOUNG_INDUSTRY = (0.05, 0.55, 0.25, 0.10, 0.03, 0.02)
YOUNG_STREET = (0.06, 0.50, 0.24, 0.12, 0.05, 0.03)
OLD_STREET = (0.02, 0.05, 0.10, 0.18, 0.40, 0.25)

LUNCH_INDUSTRY = (0.02, 0.10, 0.45, 0.20, 0.18, 0.05)
LUNCH_STREET = (0.03, 0.12, 0.42, 0.22, 0.16, 0.05)
NIGHT_STREET = (0.20, 0.05, 0.06, 0.09, 0.25, 0.35)

BALANCED_GENDER = (0.5, 0.5)


def _evaluate(
    age_street, hour_street, saturation=0.5, closure=0.5, operating=0.5, has_store=True
):
    return evaluate(
        industry_age_share=YOUNG_INDUSTRY,
        industry_gender_share=BALANCED_GENDER,
        industry_hour_share=LUNCH_INDUSTRY,
        floating_age_share=age_street,
        floating_gender_share=BALANCED_GENDER,
        floating_hour_share=hour_street,
        saturation_percentile=saturation,
        closure_rate_percentile=closure,
        operating_months_percentile=operating,
        has_store=has_store,
    )


# --- 코사인 -----------------------------------------------------------------

def test_같은_분포는_유사도_1이다():
    assert cosine(YOUNG_INDUSTRY, YOUNG_INDUSTRY) == pytest.approx(1.0)


def test_빈_분포는_판단을_보류한다():
    """자료가 없는 것과 '안 맞는다'는 다르다 — 0이 아니라 0.5."""
    assert cosine((0.0,) * 6, YOUNG_INDUSTRY) == 0.5


def test_길이가_다르면_거부한다():
    with pytest.raises(ValueError):
        cosine((0.5, 0.5), YOUNG_INDUSTRY)


# --- 적합도 -----------------------------------------------------------------

def test_잘_맞는_입지가_안_맞는_입지보다_높다():
    good = _evaluate(YOUNG_STREET, LUNCH_STREET)
    bad = _evaluate(OLD_STREET, NIGHT_STREET)
    assert good.total_score > bad.total_score


def test_종합점수는_항상_0과_1_사이다():
    cases = [
        _evaluate(YOUNG_STREET, LUNCH_STREET, saturation=0.0, closure=0.0, operating=1.0),
        _evaluate(OLD_STREET, NIGHT_STREET, saturation=1.0, closure=1.0, operating=0.0),
        _evaluate((0.0,) * 6, (0.0,) * 6),
    ]
    for result in cases:
        assert 0.0 <= result.total_score <= 1.0


def test_포화된_상권은_감점된다():
    empty = _evaluate(YOUNG_STREET, LUNCH_STREET, saturation=0.05)
    crowded = _evaluate(YOUNG_STREET, LUNCH_STREET, saturation=0.95)
    assert empty.total_score > crowded.total_score


def test_폐업률이_높으면_감점되고_오래_버티면_가점된다():
    risky = _evaluate(YOUNG_STREET, LUNCH_STREET, closure=0.95, operating=0.05)
    stable = _evaluate(YOUNG_STREET, LUNCH_STREET, closure=0.05, operating=0.95)
    assert stable.total_score > risky.total_score


def test_네_축이_모두_보고된다():
    result = _evaluate(YOUNG_STREET, LUNCH_STREET)
    assert [c.key for c in result.components] == [
        "demand_match",
        "hour_match",
        "saturation",
        "survival",
    ]
    assert sum(c.weight for c in result.components) == pytest.approx(1.0)
    assert all(0.0 <= c.score <= 1.0 for c in result.components)


def test_점포_자료가_없으면_경쟁_여유를_만점으로_주지_않는다():
    """자료 없음(백분위 전부 0)이 '경쟁자가 없다'로 읽히면 기록 없는 상권이 1등이 된다."""
    unknown = _evaluate(
        YOUNG_STREET, LUNCH_STREET, saturation=0.0, closure=0.0, operating=0.0, has_store=False
    )
    scores = {c.key: c.score for c in unknown.components}
    assert scores["saturation"] == 0.5  # 판단 보류 — cosine의 빈 분포와 같은 규칙
    assert scores["survival"] == 0.5

    empty_area = _evaluate(
        YOUNG_STREET, LUNCH_STREET, saturation=0.05, closure=0.05, operating=0.95
    )
    assert empty_area.total_score > unknown.total_score  # 실제로 한산한 상권이 더 높아야 한다


def test_백분위가_범위를_벗어나도_안전하다():
    """상류 계산이 1.2를 넘겨줘도 종합점수가 범위를 벗어나지 않는다."""
    result = _evaluate(YOUNG_STREET, LUNCH_STREET, saturation=1.5, closure=-0.3, operating=2.0)
    assert 0.0 <= result.total_score <= 1.0
