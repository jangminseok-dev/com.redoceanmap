from game.domain.commerce.customer_sampler import (
    AGE_LABELS,
    HOUR_LABELS,
    SAMPLE_SIZE,
    pick,
    sample_customers,
    summarize,
)

YOUNG = (0.02, 0.60, 0.20, 0.10, 0.05, 0.03)
OLD = (0.01, 0.04, 0.10, 0.15, 0.40, 0.30)
LUNCH = (0.02, 0.10, 0.45, 0.20, 0.18, 0.05)


def _sample(age_share=YOUNG, hour_share=LUNCH, store_id=1, day=10):
    return sample_customers(
        store_id=store_id,
        game_day=day,
        hour_share=hour_share,
        gender_share=(0.5, 0.5),
        age_share=age_share,
    )


def test_역변환_샘플링은_비중이_큰_쪽을_많이_고른다():
    assert pick(YOUNG, AGE_LABELS, 0.0) == "10대"
    assert pick(YOUNG, AGE_LABELS, 0.5) == "20대"  # 누적 0.02~0.62 구간
    assert pick(YOUNG, AGE_LABELS, 0.999) == "60대 이상"


def test_빈_분포는_균등분포로_위장하지_않는다():
    assert pick((0.0,) * 6, AGE_LABELS, 0.7) == AGE_LABELS[0]


def test_표본_크기는_고정이다():
    """하루 1,000명이 와도 객체는 40개만 만든다 — 나머지는 집계다."""
    assert len(_sample()) == SAMPLE_SIZE


def test_같은_가게_같은_날이면_같은_손님이_온다():
    assert _sample() == _sample()


def test_다른_날이면_다른_손님이_온다():
    assert _sample(day=10) != _sample(day=11)


def test_다른_가게면_다른_손님이_온다():
    assert _sample(store_id=1) != _sample(store_id=2)


def test_상권_분포가_손님_구성을_바꾼다():
    """상권마다 오는 사람이 다르다는 것이 이 게임의 전제다."""
    young_top = summarize(_sample(age_share=YOUNG), "age")[0][0]
    old_top = summarize(_sample(age_share=OLD), "age")[0][0]
    assert young_top == "20대"
    assert old_top in ("50대", "60대 이상")


def test_점심_상권이면_점심에_몰린다():
    top_hour = summarize(_sample(hour_share=LUNCH), "hour")[0][0]
    assert top_hour == "11-14시"


def test_집계는_많은_순이고_합이_표본_수다():
    buckets = summarize(_sample(), "age")
    counts = [c for _, c in buckets]
    assert counts == sorted(counts, reverse=True)
    assert sum(counts) == SAMPLE_SIZE


def test_모든_손님은_네_축을_갖는다():
    for customer in _sample():
        assert customer.hour in HOUR_LABELS
        assert customer.age in AGE_LABELS
        assert customer.gender in ("남성", "여성")
        assert customer.taste
