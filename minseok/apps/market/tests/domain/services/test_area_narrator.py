from market.domain.services.area_narrator import narrate
from market.domain.value_objects.area_profile_vo import (
    FloatingRhythm,
    ResidentProfile,
    SalesMix,
    SpendingCategory,
    SpendingProfile,
    WorkingProfile,
)


def _sales(
    weekday=850, weekend=150,
    by_time=None, by_day=None, by_gender=None, by_age=None, count=1000, monthly=0,
    weekday_count=0, weekend_count=0, count_by_age=None,
):
    flat_day = {d: 100 for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    flat_time = {t: 100 for t in ("t00_06", "t06_11", "t11_14", "t14_17", "t17_21", "t21_24")}
    return SalesMix(
        year_quarter=20244,
        weekday_amount=weekday,
        weekend_amount=weekend,
        by_day=by_day or flat_day,
        by_time=by_time or flat_time,
        by_gender=by_gender or {"male": 500, "female": 500},
        by_age=by_age or {k: 100 for k in ("age10", "age20", "age30", "age40", "age50", "age60Plus")},
        monthly_count=count,
        monthly_amount=monthly,
        weekday_count=weekday_count,
        weekend_count=weekend_count,
        count_by_age=count_by_age,
    )


def _resident(total=10000, households=100, apt=30):
    return ResidentProfile(
        year_quarter=20244, total=total, by_age=[],
        total_households=households, apartment_households=apt,
    )


def _working(total=10000):
    return WorkingProfile(year_quarter=20244, total=total, by_age=[])


def _by_key(insights):
    return {i.key: i for i in insights}


def test_전부_결측이면_빈_리스트():
    assert narrate(None, None, None, None) == []


def test_주말_비중_경계_45퍼센트는_나들이형():
    got = _by_key(narrate(_sales(weekday=550, weekend=450), None, None, None))
    assert "주말 매출 비중이 45%" in got["sales_rhythm_weekend"].text


def test_주말_비중_경계_15퍼센트는_평일_중심():
    got = _by_key(narrate(_sales(weekday=850, weekend=150), None, None, None))
    assert "주중 매출이 85%" in got["sales_rhythm_weekend"].text


def test_주말_비중_중간은_고른_분포():
    got = _by_key(narrate(_sales(weekday=700, weekend=300), None, None, None))
    assert "고르게 분포" in got["sales_rhythm_weekend"].text


def test_피크_시간대와_요일이_함께_잡히면_병기한다():
    by_time = {"t00_06": 0, "t06_11": 0, "t11_14": 300, "t14_17": 100,
               "t17_21": 400, "t21_24": 200}  # 저녁 40%
    by_day = {"mon": 100, "tue": 100, "wed": 100, "thu": 100,
              "fri": 300, "sat": 150, "sun": 150}  # 금요일 30%
    got = _by_key(narrate(_sales(by_time=by_time, by_day=by_day), None, None, None))
    text = got["sales_rhythm_peak"].text
    assert "저녁(17~21시)" in text
    assert "금요일" in text


def test_피크_미달이면_피크_문장이_없다():
    got = _by_key(narrate(_sales(), None, None, None))
    assert "sales_rhythm_peak" not in got


def test_성별_60퍼센트_경계에서_언급한다():
    got = _by_key(narrate(_sales(by_gender={"male": 400, "female": 600}), None, None, None))
    assert "여성 고객 매출이 60%" in got["customer_gender"].text


def test_성별_60퍼센트_미만이면_생략():
    got = _by_key(narrate(_sales(by_gender={"male": 401, "female": 599}), None, None, None))
    assert "customer_gender" not in got


def test_핵심_연령대_30퍼센트_경계에서_언급한다():
    by_age = {"age10": 0, "age20": 300, "age30": 700, "age40": 0, "age50": 0, "age60Plus": 0}
    got = _by_key(narrate(_sales(by_age=by_age), None, None, None))
    assert "30대 고객이 매출의 70%" in got["customer_age"].text


def test_직장_상주_2배_이상이면_오피스_상권():
    got = _by_key(narrate(None, _resident(total=10000), _working(total=20000), None))
    assert "오피스 상권" in got["demand_type"].text
    assert got["demand_type"].tone == "positive"


def test_직장_상주_절반_이하면_주거_상권():
    got = _by_key(narrate(None, _resident(total=20000), _working(total=10000), None))
    assert "주거 상권" in got["demand_type"].text


def test_그_사이면_혼합_상권():
    got = _by_key(narrate(None, _resident(total=10000), _working(total=10000), None))
    assert "혼합 상권" in got["demand_type"].text


def test_한쪽_인구가_없으면_유형_판정을_생략한다():
    got = _by_key(narrate(None, _resident(), None, None))
    assert "demand_type" not in got


def test_아파트_가구_절반_이상이면_언급한다():
    got = _by_key(narrate(None, _resident(households=100, apt=50), None, None))
    assert "50%가 아파트" in got["demand_apartment"].text


def test_아파트_가구_절반_미만이면_생략():
    got = _by_key(narrate(None, _resident(households=100, apt=49), None, None))
    assert "demand_apartment" not in got


def test_소득과_최대_지출_카테고리를_서술한다():
    spending = SpendingProfile(
        year_quarter=20244,
        monthly_avg_income=4_120_000,
        total_expenditure=9_000_000,
        by_category=[
            SpendingCategory(key="food", label="식료품", amount=3_000_000),
            SpendingCategory(key="leisure", label="여가", amount=1_000_000),
        ],
    )
    got = _by_key(narrate(None, None, None, spending))
    text = got["spending_power"].text
    assert "412만원" in text
    assert "식료품" in text


def test_객단가는_성별_매출합을_건수로_나눈다():
    got = _by_key(narrate(
        _sales(by_gender={"male": 7_000_000, "female": 7_000_000}, count=1000),
        None, None, None,
    ))
    assert "약 1.4만원" in got["avg_ticket"].text


def test_건수가_0이면_객단가를_생략한다():
    got = _by_key(narrate(_sales(count=0), None, None, None))
    assert "avg_ticket" not in got


def test_객단가는_월_총매출을_성별_합보다_우선한다():
    got = _by_key(narrate(
        _sales(by_gender={"male": 1, "female": 1}, count=1000, monthly=14_000_000),
        None, None, None,
    ))
    assert "약 1.4만원" in got["avg_ticket"].text


# --- 객단가 분해·통행 대조 (건수 축·요일 축 활용) ---

def _keys(insights):
    return {i.key for i in insights}


def _text(insights, key):
    return next(i.text for i in insights if i.key == key)


def test_주말_객단가가_뚜렷이_높으면_언급한다():
    # 주말 150,000/5건 = 3만원 vs 주중 850,000/100건 = 8,500원 — 매출은 주중이 크지만
    # 한 명당 지출은 주말이 크다. 금액만 봐서는 안 보이는 구조다.
    sales = _sales(weekday=850_000, weekend=150_000, weekday_count=100, weekend_count=5)
    text = _text(narrate(sales, None, None, None), "avg_ticket_rhythm")
    assert text.startswith("주말 객단가가 3.0만원으로 반대편(8,500원)보다")


def test_객단가_차이가_임계_미만이면_생략한다():
    # 주중 850/100=8.5, 주말 150/18≈8.3 → 2% 차이
    sales = _sales(weekday=850_000, weekend=150_000, weekday_count=100, weekend_count=18)
    assert "avg_ticket_rhythm" not in _keys(narrate(sales, None, None, None))


def test_건수가_0이면_객단가_분해를_시도하지_않는다():  # 0 나눗셈 방어
    sales = _sales(weekday_count=0, weekend_count=0, count_by_age=None)
    keys = _keys(narrate(sales, None, None, None))
    assert "avg_ticket_rhythm" not in keys and "avg_ticket_age" not in keys


def test_가장_비싸게_쓰는_연령대를_집는다():
    # 40대는 매출 500·건수 10 = 5만원으로 최고. 20대는 300·건수 500 = 600원
    sales = _sales(
        by_age={"age10": 50, "age20": 300_000, "age30": 50, "age40": 500_000,
                "age50": 50, "age60Plus": 50},
        count_by_age={"age10": 100, "age20": 500, "age30": 100, "age40": 100,
                      "age50": 100, "age60Plus": 100},
        count=1000,
    )
    assert "40대 객단가가" in _text(narrate(sales, None, None, None), "avg_ticket_age")


def test_표본이_극소한_연령대는_객단가_최고로_뽑지_않는다():
    # 10대는 건수 5건(0.5%)으로 단가 20만원이지만 허위 최고가 — 임계(5%) 미달로 제외
    sales = _sales(
        by_age={"age10": 1_000_000, "age20": 100_000, "age30": 50, "age40": 50,
                "age50": 50, "age60Plus": 50},
        count_by_age={"age10": 5, "age20": 200, "age30": 100, "age40": 100,
                      "age50": 100, "age60Plus": 100},
        count=1000,
    )
    assert "10대" not in _text(narrate(sales, None, None, None), "avg_ticket_age")


def test_통행은_주말인데_매출은_평일이면_경고한다():
    # 통행 주말 비중 50%, 매출 주말 비중 15% → 35%p 괴리
    sales = _sales(weekday=850, weekend=150)
    floating = FloatingRhythm(year_quarter=20244, weekday_pop=500, weekend_pop=500)
    got = narrate(sales, None, None, None, floating)
    insight = next(i for i in got if i.key == "traffic_vs_sales")
    assert insight.tone == "warning"
    assert "지갑은 평일에 열리는" in insight.text


def test_주말_전환이_좋으면_긍정으로_말한다():
    # 통행 주말 20%, 매출 주말 50% → -30%p
    sales = _sales(weekday=500, weekend=500)
    floating = FloatingRhythm(year_quarter=20244, weekday_pop=800, weekend_pop=200)
    insight = next(i for i in narrate(sales, None, None, None, floating)
                   if i.key == "traffic_vs_sales")
    assert insight.tone == "positive"


def test_통행_매출_괴리가_작으면_생략한다():
    sales = _sales(weekday=850, weekend=150)  # 매출 주말 15%
    floating = FloatingRhythm(year_quarter=20244, weekday_pop=800, weekend_pop=200)  # 통행 20%
    assert "traffic_vs_sales" not in _keys(narrate(sales, None, None, None, floating))


def test_통행_데이터가_없으면_교차_문장을_만들지_않는다():  # 열화
    assert "traffic_vs_sales" not in _keys(narrate(_sales(), None, None, None, None))
