from __future__ import annotations

from market.domain.value_objects.area_profile_vo import (
    ApartmentProfile,
    FacilityProfile,
    FloatingRhythm,
    ResidentProfile,
    SalesMix,
    SpendingProfile,
    WorkingProfile,
)
from market.domain.value_objects.insight_vo import Insight

# 임계값 — 경계 동작은 테스트로 고정한다
WEEKEND_HIGH = 0.45   # 주말 비중 이 이상이면 나들이·외식형
WEEKEND_LOW = 0.15    # 주말 비중 이 이하면 평일 수요 중심
PEAK_TIME_MIN = 0.35  # 시간대 최대 비중 언급 기준
PEAK_DAY_MIN = 0.20   # 요일 최대 비중 병기 기준
GENDER_MIN = 0.60     # 우세 성별 언급 기준
AGE_MIN = 0.30        # 핵심 연령대 언급 기준
OFFICE_RATIO = 2.0    # 직장/상주 비 이 이상이면 오피스형
RESIDENT_RATIO = 0.5  # 직장/상주 비 이 이하면 주거형
APT_SHARE_MIN = 0.5   # 아파트 가구 비중 언급 기준
TICKET_GAP_MIN = 0.20         # 주중/주말 객단가 차이 이 이상일 때만 언급
AGE_TICKET_MIN_SHARE = 0.05   # 건수 비중이 이 미만인 연령대는 객단가 후보에서 제외(허위 최고가 방지)
TRAFFIC_SALES_GAP_MIN = 0.15  # 통행-매출 주말 비중 괴리 이 이상일 때만 언급
BUS_STOP_MIN = 30             # 버스정거장 이 이상이면 대중교통 동선이 뚜렷하다고 본다
# 아파트 분포 임계값 — 전부 최신 분기 1,463상권 실측 분위수에서 잡았다(지어낸 값이 아니다).
HIGH_PRICE_SHARE_MIN = 0.30   # 4억 이상 세대 비중. 중앙 0.2%·p75 11.8%·p90 46.7%로 극단 편중
SMALL_UNIT_SHARE_MIN = 0.85   # 66㎡ 미만 비중. 중앙 65.9%·p75 89.5% — 서울 기본값이 소형이라 높게 잡는다
LARGE_UNIT_SHARE_MIN = 0.10   # 132㎡ 이상 비중. p90이 5.7%라 희소하지만 뜨면 성격이 뚜렷하다

# 상권 성격 임계값 — 최신 분기 1,578상권 실측. 서울 시설 데이터는 매우 희소해서
# (학교·야간체류 중앙 0·p90 1) 상식적인 "5곳 이상" 같은 기준을 쓰면 아무 상권도 뜨지 않는다.
GATEWAY_MIN = 1      # 철도역·터미널·공항 보유 상권이 서울 통틀어 3곳뿐 — 있으면 그게 그 상권의 정체다
SCHOOL_MIN = 2       # 22상권(1.4%). 1곳은 동네 어디에나 있어 "학원가"라 부를 근거가 못 된다
NIGHTLIFE_MIN = 3    # 42상권(2.7%)
CONVENIENCE_MIN = 10  # 172상권(11%) — 가장 흔해서 마지막 순위

_HIGH_PRICE_KEYS = ("b4", "b5", "over6b")
_LARGE_AREA_KEYS = ("a132", "a165")

_TIME_LABELS = {
    "t00_06": "새벽(00~06시)",
    "t06_11": "오전(06~11시)",
    "t11_14": "점심(11~14시)",
    "t14_17": "오후(14~17시)",
    "t17_21": "저녁(17~21시)",
    "t21_24": "밤(21~24시)",
}
_DAY_LABELS = {
    "mon": "월요일", "tue": "화요일", "wed": "수요일", "thu": "목요일",
    "fri": "금요일", "sat": "토요일", "sun": "일요일",
}
_AGE_LABELS = {
    "age10": "10대", "age20": "20대", "age30": "30대",
    "age40": "40대", "age50": "50대", "age60Plus": "60대 이상",
}
_GENDER_LABELS = {"male": "남성", "female": "여성"}


def narrate(
    sales: SalesMix | None,
    resident: ResidentProfile | None,
    working: WorkingProfile | None,
    spending: SpendingProfile | None,
    floating: FloatingRhythm | None = None,
    facility: FacilityProfile | None = None,
    apartment: ApartmentProfile | None = None,
) -> list[Insight]:
    """최신 분기 구조 수치 → 초보자용 해석 문장. 결측 축은 해당 문장을 생략한다."""
    insights: list[Insight] = []
    if sales is not None:
        insights += _sales_insights(sales)
    insights += _demand_insights(resident, working)
    insights += _apartment_insights(apartment)
    if spending is not None:
        insights += _spending_insights(spending)
    if sales is not None:
        for maker in (_avg_ticket, _avg_ticket_rhythm, _avg_ticket_age):
            got = maker(sales)
            if got is not None:
                insights.append(got)
        crossed = _traffic_vs_sales(sales, floating)
        if crossed is not None:
            insights.append(crossed)
    anchor = _facility_insight(facility)
    if anchor is not None:
        insights.append(anchor)
    character = _facility_character(facility)
    if character is not None:
        insights.append(character)
    return insights


def _sales_insights(sales: SalesMix) -> list[Insight]:
    out: list[Insight] = []
    total_wk = sales.weekday_amount + sales.weekend_amount
    if total_wk > 0:
        weekend_ratio = sales.weekend_amount / total_wk
        weekend_pct = round(weekend_ratio * 100)
        if weekend_ratio >= WEEKEND_HIGH:
            text = f"주말 매출 비중이 {weekend_pct}% — 나들이·외식 수요가 큰 상권입니다."
        elif weekend_ratio <= WEEKEND_LOW:
            text = f"주중 매출이 {100 - weekend_pct}% — 직장인 평일 수요 중심 상권입니다."
        else:
            text = f"주중 {100 - weekend_pct}%·주말 {weekend_pct}%로 매출이 고르게 분포합니다."
        out.append(Insight(key="sales_rhythm_weekend", tone="neutral", text=text))

    peak = _peak_text(sales)
    if peak is not None:
        out.append(peak)

    gender = _dominant(sales.by_gender)
    if gender is not None:
        key, ratio = gender
        if ratio >= GENDER_MIN:
            out.append(Insight(
                key="customer_gender", tone="neutral",
                text=f"{_GENDER_LABELS[key]} 고객 매출이 {round(ratio * 100)}% — "
                     f"{_GENDER_LABELS[key]} 고객 비중이 뚜렷한 상권입니다.",
            ))

    age = _dominant(sales.by_age)
    if age is not None:
        key, ratio = age
        if ratio >= AGE_MIN:
            out.append(Insight(
                key="customer_age", tone="neutral",
                text=f"{_AGE_LABELS[key]} 고객이 매출의 {round(ratio * 100)}%로 핵심 고객층입니다.",
            ))
    return out


def _peak_text(sales: SalesMix) -> Insight | None:
    time_top = _dominant(sales.by_time)
    day_top = _dominant(sales.by_day)
    time_hit = time_top is not None and time_top[1] >= PEAK_TIME_MIN
    day_hit = day_top is not None and day_top[1] >= PEAK_DAY_MIN
    if time_hit and day_hit:
        text = (
            f"매출의 {round(time_top[1] * 100)}%가 {_TIME_LABELS[time_top[0]]}에 집중되고, "
            f"{_DAY_LABELS[day_top[0]]} 매출이 가장 큽니다."
        )
    elif time_hit:
        text = f"매출의 {round(time_top[1] * 100)}%가 {_TIME_LABELS[time_top[0]]}에 집중됩니다."
    elif day_hit:
        text = f"요일 중에는 {_DAY_LABELS[day_top[0]]} 매출이 {round(day_top[1] * 100)}%로 가장 큽니다."
    else:
        return None
    return Insight(key="sales_rhythm_peak", tone="neutral", text=text)


def _demand_insights(
    resident: ResidentProfile | None, working: WorkingProfile | None
) -> list[Insight]:
    out: list[Insight] = []
    if resident is not None and working is not None and resident.total > 0 and working.total > 0:
        ratio = working.total / resident.total
        if ratio >= OFFICE_RATIO:
            out.append(Insight(
                key="demand_type", tone="positive",
                text=f"직장인구 {_pop(working.total)}명이 상주인구의 {ratio:.1f}배 — "
                     "평일 점심·저녁 장사에 유리한 오피스 상권입니다.",
            ))
        elif ratio <= RESIDENT_RATIO:
            out.append(Insight(
                key="demand_type", tone="neutral",
                text=f"상주인구 {_pop(resident.total)}명이 직장인구의 {1 / ratio:.1f}배 — "
                     "저녁·주말 동네 수요 중심의 주거 상권입니다.",
            ))
        else:
            out.append(Insight(
                key="demand_type", tone="neutral",
                text=f"직장인구 {_pop(working.total)}명·상주인구 {_pop(resident.total)}명 — "
                     "주중·주말 수요가 섞인 혼합 상권입니다.",
            ))
    if resident is not None and resident.total_households > 0:
        share = resident.apartment_households / resident.total_households
        if share >= APT_SHARE_MIN:
            out.append(Insight(
                key="demand_apartment", tone="positive",
                text=f"배후 가구의 {round(share * 100)}%가 아파트 — 고정 주거 수요가 탄탄합니다.",
            ))
    return out


def _share(bands: dict[str, int] | None, keys: tuple[str, ...]) -> float | None:
    """구간 분포에서 관심 구간의 비중 — 합계 0이거나 분포가 없으면 None."""
    if not bands:
        return None
    total = sum(bands.values())
    if total <= 0:
        return None
    return sum(bands.get(k, 0) for k in keys) / total


def _apartment_insights(apartment: ApartmentProfile | None) -> list[Insight]:
    """배후 아파트의 가격·평형 구성 — 평균값이 못 보는 '어떤 사람이 사는가'.

    avg_price만으로는 고가 단지 하나가 섞인 상권과 고르게 중가인 상권이 같아 보인다.
    """
    if apartment is None:
        return []
    out: list[Insight] = []
    high = _share(apartment.price_bands, _HIGH_PRICE_KEYS)
    if high is not None and high >= HIGH_PRICE_SHARE_MIN:
        out.append(Insight(
            key="demand_purchasing_power", tone="positive",
            text=f"배후 아파트의 {round(high * 100)}%가 4억 이상 구간 — "
                 "구매력이 높은 배후 수요입니다.",
        ))
    large = _share(apartment.area_bands, _LARGE_AREA_KEYS)
    small = _share(apartment.area_bands, ("under66",))
    # 서울 상권 대다수가 소형 우위라 중대형이 뜨는 쪽이 더 드물고 정보량이 크다
    if large is not None and large >= LARGE_UNIT_SHARE_MIN:
        out.append(Insight(
            key="demand_unit_size", tone="neutral",
            text=f"배후 아파트의 {round(large * 100)}%가 132㎡ 이상 중대형 — "
                 "가족 단위 수요가 두터운 상권입니다.",
        ))
    elif small is not None and small >= SMALL_UNIT_SHARE_MIN:
        out.append(Insight(
            key="demand_unit_size", tone="neutral",
            text=f"배후 아파트의 {round(small * 100)}%가 66㎡ 미만 소형 — "
                 "1~2인 가구 중심 상권입니다.",
        ))
    return out


def _spending_insights(spending: SpendingProfile) -> list[Insight]:
    income = spending.monthly_avg_income
    top = spending.by_category[0] if spending.by_category else None
    if income and top:
        text = f"배후 주민 월평균 소득은 약 {_money(income)}, {top.label} 지출 비중이 가장 큽니다."
    elif income:
        text = f"배후 주민 월평균 소득은 약 {_money(income)}입니다."
    elif top:
        text = f"배후 주민 지출은 {top.label} 비중이 가장 큽니다."
    else:
        return []
    return [Insight(key="spending_power", tone="neutral", text=text)]


def _avg_ticket(sales: SalesMix) -> Insight | None:
    # 월 총매출 우선 — 성별 미상 매출이 빠진 성별 합은 폴백으로만 쓴다
    total = sales.monthly_amount if sales.monthly_amount > 0 else sum(sales.by_gender.values())
    if total <= 0 or sales.monthly_count <= 0:
        return None
    per = total / sales.monthly_count
    if per >= 10_000:
        fmt = f"{per / 10_000:.1f}만원"
    else:
        fmt = f"{per:,.0f}원"
    return Insight(
        key="avg_ticket", tone="neutral",
        text=f"건당 평균 결제액은 약 {fmt}입니다.",
    )


def _ticket(amount: int, count: int) -> float | None:
    return amount / count if amount > 0 and count > 0 else None


def _avg_ticket_rhythm(sales: SalesMix) -> Insight | None:
    """주중 vs 주말 객단가 — 차이가 뚜렷할 때만. 주말 집중 전략의 직접 근거."""
    weekday = _ticket(sales.weekday_amount, sales.weekday_count)
    weekend = _ticket(sales.weekend_amount, sales.weekend_count)
    if weekday is None or weekend is None:
        return None
    hi, lo = max(weekday, weekend), min(weekday, weekend)
    if lo <= 0 or (hi - lo) / lo < TICKET_GAP_MIN:
        return None
    label = "주말" if weekend > weekday else "주중"
    return Insight(
        key="avg_ticket_rhythm", tone="neutral",
        text=f"{label} 객단가가 {_won(hi)}으로 반대편({_won(lo)})보다 "
             f"{round((hi - lo) / lo * 100)}% 높습니다.",
    )


def _avg_ticket_age(sales: SalesMix) -> Insight | None:
    """가장 비싸게 쓰는 연령대 — 매출 최다층과 다를 때 특히 값어치가 있다.

    (방문은 20대인데 지갑은 40대, 같은 구조를 드러낸다.)
    """
    counts = sales.count_by_age
    if not counts or sales.monthly_count <= 0:
        return None
    best: tuple[str, float] | None = None
    for key, count in counts.items():
        # 표본이 극소한 연령대가 허위 최고가로 뽑히는 것을 막는다
        if count < sales.monthly_count * AGE_TICKET_MIN_SHARE:
            continue
        per = _ticket(sales.by_age.get(key, 0), count)
        if per is not None and (best is None or per > best[1]):
            best = (key, per)
    if best is None:
        return None
    key, per = best
    return Insight(
        key="avg_ticket_age", tone="neutral",
        text=f"{_AGE_LABELS[key]} 객단가가 {_won(per)}으로 가장 높습니다.",
    )


def _traffic_vs_sales(sales: SalesMix, floating: FloatingRhythm | None) -> Insight | None:
    """통행 리듬과 매출 리듬의 괴리 — 어느 한쪽만으로는 만들 수 없는 인사이트."""
    if floating is None:
        return None
    traffic_total = floating.weekday_pop + floating.weekend_pop
    sales_total = sales.weekday_amount + sales.weekend_amount
    if traffic_total <= 0 or sales_total <= 0:
        return None
    traffic_weekend = floating.weekend_pop / traffic_total
    sales_weekend = sales.weekend_amount / sales_total
    gap = traffic_weekend - sales_weekend
    if abs(gap) < TRAFFIC_SALES_GAP_MIN:
        return None
    t_pct, s_pct = round(traffic_weekend * 100), round(sales_weekend * 100)
    if gap > 0:
        text = (f"주말 통행은 {t_pct}%인데 매출은 {s_pct}% — "
                "지나가긴 해도 지갑은 평일에 열리는 상권입니다.")
        tone = "warning"
    else:
        text = (f"주말 통행은 {t_pct}%인데 매출은 {s_pct}% — "
                "주말 방문객이 실제 구매로 잘 이어집니다.")
        tone = "positive"
    return Insight(key="traffic_vs_sales", tone=tone, text=text)


def _facility_insight(facility: FacilityProfile | None) -> Insight | None:
    """외부 유입 동선의 앵커 — 역·대학·백화점·버스정거장. 하나도 없으면 침묵한다.

    시설 20종을 다 세면 숫자 나열이다. "이 상권에 사람이 왜 오는가"를 만드는 것만 센다.
    """
    if facility is None:
        return None
    parts = []
    if facility.subway_stations:
        parts.append(f"지하철역 {facility.subway_stations}곳")
    if facility.universities:
        parts.append(f"대학 {facility.universities}곳")
    if facility.department_stores:
        parts.append(f"백화점 {facility.department_stores}곳")
    if facility.bus_stops >= BUS_STOP_MIN:
        parts.append(f"버스정거장 {facility.bus_stops}개")
    if not parts:
        return None
    return Insight(
        key="facility_anchor", tone="positive",
        text=" · ".join(parts) + " — 외부 유입 동선이 강한 상권입니다.",
    )


def _facility_character(facility: FacilityProfile | None) -> Insight | None:
    """상권의 성격 — "사람이 왜 오는가"가 같은 시설끼리 묶어 하나만 말한다.

    `_facility_insight`(유입 동선의 세기)와 축이 다르다. 이쪽은 유입의 *종류*다.
    희소한 축이 정보량이 크므로 광역관문 → 학교 → 야간체류 → 생활편의 순으로 보고
    **처음 걸리는 하나만** 낸다. 넷을 다 나열하면 시설 13종을 세는 것과 다를 게 없다.
    """
    if facility is None:
        return None
    if facility.gateway >= GATEWAY_MIN:
        return Insight(
            key="facility_character", tone="positive",
            text=f"철도역·터미널 {facility.gateway}곳 — 서울 밖에서 들어오는 광역 유입 상권입니다.",
        )
    if facility.schools >= SCHOOL_MIN:
        return Insight(
            key="facility_character", tone="neutral",
            text=f"학교·유치원 {facility.schools}곳 — 학생·학부모 동선이 굵은 상권입니다.",
        )
    if facility.nightlife >= NIGHTLIFE_MIN:
        return Insight(
            key="facility_character", tone="neutral",
            text=f"극장·숙박 {facility.nightlife}곳 — 밤과 주말에 머무는 수요가 있는 상권입니다.",
        )
    if facility.convenience >= CONVENIENCE_MIN:
        return Insight(
            key="facility_character", tone="neutral",
            text=f"은행·약국·마트 등 생활시설 {facility.convenience}곳 — "
                 "동네 생활 동선이 지나는 상권입니다.",
        )
    return None


def _won(v: float) -> str:
    return f"{v / 10_000:.1f}만원" if v >= 10_000 else f"{v:,.0f}원"


def _dominant(values: dict[str, int]) -> tuple[str, float] | None:
    """최댓값 키와 전체 대비 비중 — 합계 0이면 None."""
    total = sum(values.values())
    if total <= 0:
        return None
    key = max(values, key=values.get)  # type: ignore[arg-type]
    return key, values[key] / total


def _pop(n: int) -> str:
    return f"{n / 10_000:.1f}만" if n >= 10_000 else f"{n:,}"


def _money(won: float) -> str:
    if won >= 100_000_000:
        return f"{won / 100_000_000:.1f}억원"
    return f"{round(won / 10_000):,}만원"
