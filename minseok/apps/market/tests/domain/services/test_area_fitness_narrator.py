import pytest

from market.domain.services.area_fitness_narrator import diagnose, josa

YOUNG_INDUSTRY = (0.05, 0.55, 0.25, 0.10, 0.03, 0.02)
OLD_STREET = (0.02, 0.05, 0.10, 0.18, 0.40, 0.25)
YOUNG_STREET = (0.06, 0.50, 0.24, 0.12, 0.05, 0.03)
LUNCH = (0.02, 0.10, 0.45, 0.20, 0.18, 0.05)
NIGHT = (0.20, 0.05, 0.06, 0.09, 0.25, 0.35)


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("커피-음료", "가"),  # 받침 없음
        ("한식음식점", "이"),  # 받침 있음
        ("치킨", "이"),
        ("스포츠 강습", "이"),
        ("PC방", "이"),
        ("CS100010", "가"),  # 숫자로 끝나면 받침 없는 쪽
        ("", "가"),
    ],
)
def test_조사는_받침에_따라_갈린다(word, expected):
    """업종명이 100종이라 '커피-음료이'처럼 어색해지는 자리가 실제로 나왔다."""
    assert josa(word, "이", "가") == expected


def _diagnose(**overrides):
    base = dict(
        service_name="커피-음료",
        industry_age_share=YOUNG_INDUSTRY,
        floating_age_share=YOUNG_STREET,
        industry_hour_share=LUNCH,
        floating_hour_share=LUNCH,
        saturation_percentile=0.3,
        closure_rate_percentile=0.3,
        similar_store_count=12,
        operating_months_avg=100.0,
        has_sales=True,
        has_store=True,
    )
    base.update(overrides)
    return diagnose(**base)


def test_잘_맞는_입지는_좋은_신호를_낸다():
    results = _diagnose()
    assert any(d.tone == "good" for d in results)
    assert not any(d.tone == "bad" for d in results)


def test_연령이_어긋나면_숫자로_지적한다():
    results = _diagnose(floating_age_share=OLD_STREET)
    bad = [d for d in results if d.tone == "bad"]
    assert bad
    assert "20대" in bad[0].message and "50대" in bad[0].message


def test_시간대가_어긋나면_지적한다():
    results = _diagnose(floating_hour_share=NIGHT)
    assert any("11-14시" in d.message and d.tone == "bad" for d in results)


def test_포화_상권은_경쟁을_지적한다():
    results = _diagnose(saturation_percentile=0.95, similar_store_count=32)
    assert any("32곳" in d.message and d.tone == "bad" for d in results)


def test_나쁜_신호가_앞에_온다():
    """읽는 사람이 먼저 봐야 할 것을 먼저 보여준다."""
    results = _diagnose(
        floating_age_share=OLD_STREET, floating_hour_share=NIGHT, saturation_percentile=0.95
    )
    tones = [d.tone for d in results]
    assert tones == sorted(tones, key=lambda t: {"bad": 0, "warn": 1, "good": 2}[t])


def test_매출_자료가_없으면_먼저_알린다():
    results = _diagnose(has_sales=False)
    assert any("매출 기록이 없습니다" in d.message for d in results)


def test_분포가_비어도_터지지_않는다():
    results = _diagnose(
        industry_age_share=(0.0,) * 6,
        floating_age_share=(0.0,) * 6,
        industry_hour_share=(0.0,) * 6,
        floating_hour_share=(0.0,) * 6,
        operating_months_avg=0.0,
        has_sales=False,
        has_store=False,
    )
    assert isinstance(results, tuple)
