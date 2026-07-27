from market.domain.services.area_narrator import narrate
from market.domain.value_objects.area_profile_vo import (
    ApartmentProfile,
    FacilityProfile,
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
    count_by_day=None, count_by_time=None, count_by_gender=None,
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
        count_by_day=count_by_day,
        count_by_time=count_by_time,
        count_by_gender=count_by_gender,
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


# --- 집객시설 앵커 ---

def _facility(subway=0, bus=0, univ=0, dept=0, hosp=0, total=0, gateway=0, schools=0, nightlife=0, conv=0):
    return FacilityProfile(
        year_quarter=20254, total=total, subway_stations=subway, bus_stops=bus,
        universities=univ, department_stores=dept, hospitals=hosp,
        gateway=gateway, schools=schools, nightlife=nightlife, convenience=conv,
    )


def test_외부_유입_앵커가_있으면_언급한다():
    got = narrate(None, None, None, None, None, _facility(subway=2, univ=1, bus=34))
    insight = next(i for i in got if i.key == "facility_anchor")
    assert insight.tone == "positive"
    assert insight.text == "지하철역 2곳 · 대학 1곳 · 버스정거장 34개 — 외부 유입 동선이 강한 상권입니다."


def test_앵커가_하나도_없으면_침묵한다():
    # 병원·소규모 정류장만 있는 동네 상권을 "유입이 강하다"고 말하면 거짓이다.
    got = narrate(None, None, None, None, None, _facility(bus=12, hosp=3, total=15))
    assert "facility_anchor" not in _keys(got)


def test_버스정거장은_임계_이상일_때만_센다():
    assert "facility_anchor" not in _keys(narrate(None, None, None, None, None, _facility(bus=29)))
    assert "facility_anchor" in _keys(narrate(None, None, None, None, None, _facility(bus=30)))


def test_집객시설_데이터가_없으면_문장을_만들지_않는다():  # 열화
    assert "facility_anchor" not in _keys(narrate(_sales(), None, None, None, None, None))


def _apartment(price=None, area=None):
    return ApartmentProfile(
        year_quarter=20254, complex_count=5, avg_price=500_000_000, avg_area=60,
        price_bands=price, area_bands=area,
    )


def _apt_narrate(price=None, area=None):
    return _keys(narrate(None, None, None, None, None, None, _apartment(price, area)))


def _price(**over):
    bands = {k: 0 for k in ("under1b", "b1", "b2", "b3", "b4", "b5", "over6b")}
    bands.update(over)
    return bands


def _area(**over):
    bands = {k: 0 for k in ("under66", "a66", "a99", "a132", "a165")}
    bands.update(over)
    return bands


def test_고가_비중_경계_30퍼센트에서_구매력_문장이_뜬다():
    # 4억 이상(b4·b5·over6b) 30/100 = 정확히 임계
    got = narrate(None, None, None, None, None, None,
                  _apartment(price=_price(under1b=70, b4=30)))
    insight = next(i for i in got if i.key == "demand_purchasing_power")
    assert insight.tone == "positive"
    assert "30%가 4억 이상" in insight.text


def test_고가_비중이_임계_미만이면_침묵한다():
    assert "demand_purchasing_power" not in _apt_narrate(price=_price(under1b=71, b4=29))


def test_아파트_분포_합이_0이면_문장을_만들지_않는다():  # 0 나눗셈 방어
    assert _apt_narrate(price=_price(), area=_area()) == set()


def test_중대형_비중이_10퍼센트_이상이면_가족_단위로_읽는다():
    got = narrate(None, None, None, None, None, None,
                  _apartment(area=_area(under66=90, a132=10)))
    insight = next(i for i in got if i.key == "demand_unit_size")
    assert "132㎡ 이상 중대형" in insight.text


def test_중대형이_없고_소형이_우세하면_1_2인_가구로_읽는다():
    got = narrate(None, None, None, None, None, None, _apartment(area=_area(under66=85, a66=15)))
    insight = next(i for i in got if i.key == "demand_unit_size")
    assert "66㎡ 미만 소형" in insight.text


def test_소형_비중이_서울_평균_수준이면_침묵한다():
    # 중앙값(65.9%) 부근은 서울의 기본값이라 "소형 중심"이라고 말할 근거가 없다
    assert "demand_unit_size" not in _apt_narrate(area=_area(under66=66, a66=34))


def test_아파트_분포가_없으면_문장을_만들지_않는다():  # 열화
    assert _apt_narrate() == set()


# --- 상권 성격 (시설 13종을 유입의 '종류'로 묶음) ---

def _char(**kw):
    got = narrate(None, None, None, None, None, _facility(**kw))
    return next((i for i in got if i.key == "facility_character"), None)


def test_광역관문이_있으면_최우선으로_말한다():
    # 철도역·터미널 보유 상권은 서울 통틀어 3곳 — 있으면 그게 그 상권의 정체다
    insight = _char(gateway=1, schools=5, nightlife=9, conv=50)
    assert insight is not None and insight.tone == "positive"
    assert "광역 유입" in insight.text


def test_광역관문이_없으면_학교가_다음_순위():
    insight = _char(schools=2, nightlife=9, conv=50)
    assert "학생·학부모 동선" in insight.text


def test_학교_1곳은_학원가로_보지_않는다():
    # 유치원 1곳은 동네 어디에나 있다 — 임계는 2
    insight = _char(schools=1, conv=50)
    assert "생활 동선" in insight.text  # 학교가 아니라 생활편의로 떨어진다


def test_야간체류는_생활편의보다_우선한다():
    insight = _char(nightlife=3, conv=50)
    assert "밤과 주말" in insight.text


def test_생활편의는_가장_흔해서_마지막이다():
    insight = _char(conv=10)
    assert "동네 생활 동선" in insight.text


def test_어느_축도_임계에_못_미치면_침묵한다():
    assert _char(schools=1, nightlife=2, conv=9) is None


def test_성격_문장은_최대_한_개다():
    # 넷을 다 나열하면 시설 13종을 세는 것과 다를 게 없다
    got = narrate(None, None, None, None, None,
                  _facility(gateway=2, schools=4, nightlife=8, conv=40))
    assert len([i for i in got if i.key == "facility_character"]) == 1


def test_시설_데이터가_없으면_성격도_말하지_않는다():  # 열화
    assert "facility_character" not in _keys(narrate(_sales(), None, None, None, None, None))


# --- 시간대·성별 객단가, 통행 성별 대조 (건수 축 15 + 통행 성별 2) ---

def test_시간대_객단가가_평균의_2배_이상이면_말한다():
    # 저녁 매출 500,000 / 건수 50 = 1만원, 전체 1,000,000 / 1000 = 1,000원 → 10배
    sales = _sales(
        by_time={"t00_06": 0, "t06_11": 0, "t11_14": 500_000, "t14_17": 0,
                 "t17_21": 500_000, "t21_24": 0},
        count_by_time={"t00_06": 0, "t06_11": 0, "t11_14": 900, "t14_17": 0,
                       "t17_21": 50, "t21_24": 0},
        count=1000, monthly=1_000_000,
    )
    text = _text(narrate(sales, None, None, None), "avg_ticket_time")
    assert "저녁(17~21시)" in text and "배입니다" in text


def test_시간대_객단가가_평균의_2배_미만이면_생략한다():
    sales = _sales(
        by_time={"t00_06": 0, "t06_11": 0, "t11_14": 500_000, "t14_17": 0,
                 "t17_21": 500_000, "t21_24": 0},
        count_by_time={"t00_06": 0, "t06_11": 0, "t11_14": 400, "t14_17": 0,
                       "t17_21": 600, "t21_24": 0},
        count=1000, monthly=1_000_000,
    )
    assert "avg_ticket_time" not in _keys(narrate(sales, None, None, None))


def test_건수가_극소한_시간대는_최고_객단가로_뽑지_않는다():
    # 새벽 40건(4%)에 단가 25만원이지만 임계(5%) 미달로 제외 — 연령 객단가와 같은 방어
    sales = _sales(
        by_time={"t00_06": 10_000_000, "t06_11": 0, "t11_14": 500_000, "t14_17": 0,
                 "t17_21": 500_000, "t21_24": 0},
        count_by_time={"t00_06": 40, "t06_11": 0, "t11_14": 900, "t14_17": 0,
                       "t17_21": 60, "t21_24": 0},
        count=1000, monthly=1_000_000,
    )
    assert "새벽" not in _text(narrate(sales, None, None, None), "avg_ticket_time")


def test_성별_객단가_격차가_뚜렷하면_말한다():
    # 남 900,000/100 = 9,000원 · 여 100,000/100 = 1,000원 → 9배
    sales = _sales(
        by_gender={"male": 900_000, "female": 100_000},
        count_by_gender={"male": 100, "female": 100},
    )
    text = _text(narrate(sales, None, None, None), "avg_ticket_gender")
    assert text.startswith("남성 객단가가")


def test_성별_객단가_격차가_임계_미만이면_생략한다():
    # 남 1,000원 · 여 1,000원
    sales = _sales(
        by_gender={"male": 100_000, "female": 100_000},
        count_by_gender={"male": 100, "female": 100},
    )
    assert "avg_ticket_gender" not in _keys(narrate(sales, None, None, None))


def test_성별_건수가_없으면_객단가_격차를_계산하지_않는다():  # 0 나눗셈 방어
    sales = _sales(count_by_gender={"male": 0, "female": 0})
    assert "avg_ticket_gender" not in _keys(narrate(sales, None, None, None))


def test_여성_통행보다_여성_매출이_높으면_전환을_말한다():
    # 통행 여성 30%, 매출 여성 70% → +40%p
    sales = _sales(by_gender={"male": 300, "female": 700})
    floating = FloatingRhythm(
        year_quarter=20244, weekday_pop=500, weekend_pop=500, male_pop=700, female_pop=300,
    )
    text = _text(narrate(sales, None, None, None, floating), "traffic_vs_sales_gender")
    assert text.startswith("여성 통행은 30%인데 매출은 70%")


def test_남성_쪽으로_기울면_남성_기준으로_말한다():
    # 통행 여성 70%, 매출 여성 30% → 남성 통행 30% · 남성 매출 70%
    sales = _sales(by_gender={"male": 700, "female": 300})
    floating = FloatingRhythm(
        year_quarter=20244, weekday_pop=500, weekend_pop=500, male_pop=300, female_pop=700,
    )
    text = _text(narrate(sales, None, None, None, floating), "traffic_vs_sales_gender")
    assert text.startswith("남성 통행은 30%인데 매출은 70%")


def test_성별_괴리가_임계_미만이면_생략한다():
    sales = _sales(by_gender={"male": 500, "female": 500})
    floating = FloatingRhythm(
        year_quarter=20244, weekday_pop=500, weekend_pop=500, male_pop=550, female_pop=450,
    )
    assert "traffic_vs_sales_gender" not in _keys(narrate(sales, None, None, None, floating))


def test_통행_성별이_없으면_성별_대조를_하지_않는다():  # 열화
    floating = FloatingRhythm(year_quarter=20244, weekday_pop=500, weekend_pop=500)
    assert "traffic_vs_sales_gender" not in _keys(narrate(_sales(), None, None, None, floating))
