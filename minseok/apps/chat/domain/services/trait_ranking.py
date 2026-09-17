"""상권 성격형 질문 결정론 랭킹 — "직장인 많은 곳 점심 장사"를 지표로 바꿔 줄 세운다(순수 함수, LLM 없음).

2026-09-17 점검: 지역·업종 없이 성격만 말한 질문(골든 MN03·MN04·MN06·MN07·MN09)은 phase1 표에 성격 열이 없어
모델이 월매출 상위를 골랐다 — "직장인 많은 곳"에 관광특구가, "대학가"에 대학 없는 상권이 섞였다.
여기서는 질문 어휘 → 보유 지표(직장인구·시간대/요일/연령 매출·상주 가구·시설)로 바꾸고, 지표마다 서울 상권
백분위를 낸 뒤 평균으로 줄 세운다. 매출 지표는 **점포당**(같은 업종 경쟁 점포 수로 나눔)이라 큰 상권만 뜨지 않는다.
데이터가 없는 성격(관광객·외국인)은 반영한 척하지 않고 없다고 말한다(I-12).

행(row)은 허브 `AreaTraitRow`와 같은 속성 이름을 가진 객체 — 도메인이 허브 DTO를 import하지 않게 속성으로만 읽는다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

DAYS_PER_QUARTER = 91          # 분기 유동인구 합계 → 일평균
MIN_AREA_STORES = 10           # 상권 전체 점포 극단값 컷(조건 질의 경로와 같은 값)
MIN_SERVICE_STORES = 5         # 점포당 매출 지표는 같은 업종 점포 5곳 이상만(9/8 소표본 규칙)
MIN_SALES_COUNT = 1_000        # 객단가·연령 비중은 월 결제 1,000건 이상만 — 건수가 적으면 한두 건이 값을 정한다
                               # (실측: 제과점 객단가 25만원, 의류 20대 비중 100%)
EATOUT_SCOPE = "CS1"           # 시간대 매출 성격인데 업종을 안 말하면 외식 전체로 본다("점심 장사")


@dataclass(frozen=True)
class Trait:
    key: str
    label: str                                   # 기준 설명 — "직장인구"
    value: Callable[[Any], float | None]
    describe: Callable[[Any], str]
    per_store_sales: bool = False                # 같은 업종 점포 수가 모수인 지표
    eatout_default: bool = False                 # 업종 미지정이면 외식 전체 범위


def _per_store(amount: int | None, row: Any) -> float | None:
    if amount is None or row.store_count < MIN_SERVICE_STORES:
        return None
    return amount / row.store_count


def _man(won: float) -> str:
    return f"{round(won / 10_000):,}만원"


def _sales_trait(key: str, label: str, attr: str, eatout: bool) -> Trait:
    name = f"점포당 {label} 월매출" if label else "점포당 월매출"
    return Trait(
        key=key, label=name,
        value=lambda r: _per_store(getattr(r, attr), r),
        describe=lambda r: f"{name} {_man(_per_store(getattr(r, attr), r) or 0)}",
        per_store_sales=True, eatout_default=eatout,
    )


def _age_trait(decade: int) -> Trait:
    idx = min(decade, 6) - 1

    def share(r: Any) -> float | None:
        if (not r.age_sales or not r.monthly_sales or (r.monthly_sales_count or 0) < MIN_SALES_COUNT
                or r.store_count < MIN_SERVICE_STORES):
            return None
        return r.age_sales[idx] / r.monthly_sales * 100

    age = "60대 이상" if decade >= 6 else f"{decade}0대"
    return Trait(key=f"age{decade}", label=f"{age} 매출 비중", value=share,
                 describe=lambda r: f"{age} 매출 비중 {share(r) or 0:.0f}%", per_store_sales=True)


def _count_trait(key: str, label: str, attr: str, unit: str, scale: float = 1.0) -> Trait:
    def value(r: Any) -> float | None:
        v = getattr(r, attr)
        return None if v is None else v / scale
    return Trait(key=key, label=label, value=value,
                 describe=lambda r: f"{label} {round(value(r) or 0):,}{unit}")


def _ticket(r: Any) -> float | None:
    if (not r.monthly_sales or (r.monthly_sales_count or 0) < MIN_SALES_COUNT
            or r.store_count < MIN_SERVICE_STORES):
        return None
    return r.monthly_sales / r.monthly_sales_count


TRAITS: dict[str, Trait] = {
    "worker": _count_trait("worker", "직장인구", "working_pop", "명"),
    "flow": _count_trait("flow", "일평균 유동인구", "floating_pop", "명", DAYS_PER_QUARTER),
    "night_flow": _count_trait("night_flow", "밤(21~06시) 일평균 유동인구", "night_floating_pop", "명", DAYS_PER_QUARTER),
    "lunch": _sales_trait("lunch", "점심(11~14시)", "lunch_sales", True),
    "dinner": _sales_trait("dinner", "저녁(17~21시)", "dinner_sales", True),
    "night": _sales_trait("night", "밤(21~06시)", "night_sales", True),
    "weekend": _sales_trait("weekend", "주말", "weekend_sales", False),
    "weekday": _sales_trait("weekday", "평일", "weekday_sales", False),
    "sales": _sales_trait("sales", "", "monthly_sales", False),
    "university": _count_trait("university", "대학", "university_count", "곳"),
    "station": _count_trait("station", "지하철역", "subway_station_count", "곳"),
    "residential": _count_trait("residential", "배후 상주 가구", "total_households", "가구"),
    "apartment": _count_trait("apartment", "아파트 가구", "apartment_households", "가구"),
    "family": _count_trait("family", "유치원·초등학교", "child_facility_count", "곳"),
    "ticket": Trait(key="ticket", label="객단가", value=_ticket,
                    describe=lambda r: f"객단가 {round(_ticket(r) or 0):,}원", per_store_sales=True),
}

# 어휘 → 성격. 앞에서부터 모두 본다(여러 성격 동시 허용).
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("worker", re.compile(r"직장인|오피스|회사원|사무실|직장\s*인구")),
    ("lunch", re.compile(r"점심|(?<!브)런치")),   # "브런치"는 점심 시간대 성격이 아니다
    ("dinner", re.compile(r"저녁|퇴근")),
    ("night", re.compile(r"밤|야간|심야|새벽")),
    ("weekend", re.compile(r"주말")),
    ("weekday", re.compile(r"평일|주중")),
    ("university", re.compile(r"대학|캠퍼스")),
    ("station", re.compile(r"역세권|지하철\s*역")),
    ("apartment", re.compile(r"아파트")),
    ("residential", re.compile(r"주거|주택가|배후\s*(?:세대|가구|수요)|동네\s*주민")),
    # "아이"만으로는 "아이템·아이디어"가 걸린다 — 아이를 뜻하는 결합형만
    ("family", re.compile(r"가족|아이(?:들|\s*(?:키우|동반|엄마|손님))|키즈|어린이|유아")),
    ("ticket", re.compile(r"객단가")),
    ("flow", re.compile(r"유동\s*인구|사람\s*(?:이|들이)?\s*많|붐비")),
)
_AGE_RE = re.compile(r"([1-6])0\s*대")
_UNSUPPORTED = (
    (re.compile(r"관광|외국인"), "관광객·외국인 비중은 데이터가 없어 반영하지 못했어요."),
)


@dataclass(frozen=True)
class TraitQuery:
    traits: tuple[Trait, ...]
    notes: tuple[str, ...]

    @property
    def labels(self) -> str:
        return "·".join(t.label for t in self.traits)

    @property
    def uses_sales(self) -> bool:
        return any(t.per_store_sales for t in self.traits)

    @property
    def eatout_default(self) -> bool:
        return any(t.eatout_default for t in self.traits)


def detect(prompt: str, condition_axes: list[str] | tuple[str, ...] = ()) -> TraitQuery | None:
    """질문의 성격 어휘를 지표로 바꾼다. 성격 어휘가 하나도 없으면 None(조건 질의·되묻기 경로에 맡긴다).

    condition_axes: 조건 질의 축("sales" — 매출 높은) 중 성격과 함께 쓸 것. 폐업률 축은 호출자가 1년 폐업률로 거른다.
    """
    keys = [key for key, pattern in _PATTERNS if pattern.search(prompt)]
    ages = sorted({int(m) for m in _AGE_RE.findall(prompt)})
    if not keys and not ages:
        return None
    if "flow" in keys and "night" in keys:   # "밤에 유동인구 많은 곳" — 밤 매출이 아니라 밤 유동인구
        keys = [k for k in keys if k not in ("flow", "night")] + ["night_flow"]
    if "apartment" in keys and "residential" in keys:
        keys.remove("residential")
    if "sales" in condition_axes:
        keys.append("sales")
    traits = tuple(TRAITS[k] for k in keys) + tuple(_age_trait(d) for d in ages)
    notes = tuple(msg for pattern, msg in _UNSUPPORTED if pattern.search(prompt))
    return TraitQuery(traits=traits, notes=notes)


def rank(rows: list[Any], query: TraitQuery) -> list[Any]:
    """성격 지표마다 서울 상권 백분위(0~1)를 내고 평균이 높은 순. 지표가 하나라도 없는 상권은 뺀다.

    백분위는 동률을 평균 순위로 — 대학 0곳 상권 수백 곳이 임의 순서로 앞서지 않게 한다.
    """
    pool = [r for r in rows if r.area_store_count >= MIN_AREA_STORES]
    values = {id(r): [t.value(r) for t in query.traits] for r in pool}
    pool = [r for r in pool if all(v is not None for v in values[id(r)])]
    if not pool:
        return []
    n = len(pool)
    score = {id(r): 0.0 for r in pool}
    for i in range(len(query.traits)):
        ordered = sorted(pool, key=lambda r: values[id(r)][i])
        pos = 0
        while pos < n:
            end = pos
            v = values[id(ordered[pos])][i]
            while end + 1 < n and values[id(ordered[end + 1])][i] == v:
                end += 1
            pct = ((pos + end) / 2) / (n - 1) if n > 1 else 1.0
            for r in ordered[pos:end + 1]:
                score[id(r)] += pct
            pos = end + 1
    return sorted(pool, key=lambda r: (-score[id(r)], -r.area_store_count))


def describe(row: Any, query: TraitQuery) -> str:
    return " · ".join(t.describe(row) for t in query.traits)
