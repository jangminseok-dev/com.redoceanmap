from types import SimpleNamespace

from chat.domain.services import trait_ranking as tr


def _row(code, **overrides):
    base = dict(
        trdar_code=code, trdar_name=f"상권{code}", district_name="중구", dong_name="명동",
        store_count=20, area_store_count=100, monthly_sales=100_000_000, monthly_sales_count=10_000,
        lunch_sales=30_000_000, dinner_sales=20_000_000, night_sales=5_000_000,
        weekend_sales=30_000_000, weekday_sales=70_000_000,
        age_sales=(1_000_000, 30_000_000, 30_000_000, 20_000_000, 10_000_000, 9_000_000),
        working_pop=1_000, floating_pop=910_000, night_floating_pop=91_000,
        total_households=500, apartment_households=100, university_count=0,
        subway_station_count=0, child_facility_count=0,
    )
    return SimpleNamespace(**{**base, **overrides})


def _labels(prompt):
    q = tr.detect(prompt)
    return q.labels if q else None


def test_골든_성격형_질문을_지표로_바꾼다():
    assert _labels("직장인 많은 곳에서 점심 장사 하려는데 어디가 좋아?") == "직장인구·점포당 점심(11~14시) 월매출"
    assert _labels("20대가 많이 다니는 동네에 옷가게 어때?") == "20대 매출 비중"
    assert _labels("대학가 근처 스터디카페 창업 어때?") == "대학"
    assert _labels("객단가 높은 동네에 디저트샵 차리려면 어디가 좋을까?") == "객단가"


def test_밤에_유동인구는_밤_매출이_아니라_밤_유동인구다():
    assert _labels("밤에 유동인구 많은 곳에 포차 어때?") == "밤(21~06시) 일평균 유동인구"


def test_동음_오탐을_막는다():
    assert _labels("주말 장사가 잘되는 곳에 브런치 카페 내고 싶어") == "점포당 주말 월매출"  # 브런치 ≠ 점심
    assert tr.detect("창업 아이템 추천해줘") is None  # 아이템 ≠ 아이
    assert tr.detect("1억으로 치킨집 차릴 만한 상권 추천해줘") is None


def test_시간대_매출_성격은_업종_미지정이면_외식_전체로_본다():
    assert tr.detect("점심 장사 할 곳").eatout_default
    assert not tr.detect("직장인 많은 곳").eatout_default


def test_데이터_없는_성격은_고지만_남긴다():
    q = tr.detect("직장인 많고 외국인 관광객도 오는 곳")
    assert q.labels == "직장인구" and "외국인" in q.notes[0]


def test_조건_축_매출은_성격과_함께_쓴다():
    assert tr.detect("직장인 많고 매출 높은 곳", ["sales"]).labels == "직장인구·점포당 월매출"


def test_성격_백분위_평균이_높은_순이다():
    q = tr.detect("직장인 많은 곳 점심 장사")
    a = _row(1, working_pop=9_000, lunch_sales=10_000_000)   # 직장인 1위, 점심 3위
    b = _row(2, working_pop=5_000, lunch_sales=60_000_000)   # 2위, 1위
    c = _row(3, working_pop=1_000, lunch_sales=20_000_000)   # 3위, 2위
    assert [r.trdar_code for r in tr.rank([a, b, c], q)] == [2, 1, 3]


def test_점포당_매출은_같은_업종_점포_5곳_미만이면_비교에서_뺀다():
    q = tr.detect("점심 장사")
    few = _row(1, store_count=4, lunch_sales=900_000_000)
    ok = _row(2)
    assert [r.trdar_code for r in tr.rank([few, ok], q)] == [2]


def test_상권_전체_점포_10곳_미만은_극단값으로_뺀다():
    q = tr.detect("직장인 많은 곳")
    assert tr.rank([_row(1, area_store_count=9, working_pop=10**6), _row(2)], q)[0].trdar_code == 2


def test_동률은_평균_순위라_0곳_상권이_앞서지_않는다():
    q = tr.detect("대학가")
    rows = [_row(i) for i in range(1, 6)] + [_row(9, university_count=2)]
    assert tr.rank(rows, q)[0].trdar_code == 9


def test_서술은_지표_값을_단위와_함께_쓴다():
    q = tr.detect("직장인 많은 곳 점심 장사")
    assert tr.describe(_row(1), q) == "직장인구 1,000명 · 점포당 점심(11~14시) 월매출 150만원"


def test_객단가는_결제_건수가_적으면_비교에서_뺀다():
    q = tr.detect("객단가 높은 곳")
    thin = _row(1, monthly_sales=10_000_000, monthly_sales_count=40)   # 25만원 — 한두 건이 값을 정한다
    assert [r.trdar_code for r in tr.rank([thin, _row(2)], q)] == [2]


def test_연령_비중도_결제_건수가_적으면_비교에서_뺀다():
    q = tr.detect("20대 많은 곳")
    thin = _row(1, monthly_sales_count=40, age_sales=(0, 100_000_000, 0, 0, 0, 0))   # 100% — 표본 잡음
    assert [r.trdar_code for r in tr.rank([thin, _row(2)], q)] == [2]
