from __future__ import annotations

from statistics import median

from market.app.dtos.area_ranking_dto import (
    AreaRankingQuery,
    AreaRankingRow,
    AreaRankingView,
    AreaShowcaseRow,
    AreaShowcaseView,
    DivisionMedian,
    DongRollupRow,
    ServiceOption,
)
from market.app.ports.input.area_ranking_use_case import AreaRankingUseCase
from market.app.ports.output.area_ranking_repository import AreaRankingRepositoryPort

# 쇼케이스 카드 수와 점포수 하한. 쿼리 파라미터로 열지 않는다 — 인증도 rate limit도
# 없는 공개 엔드포인트에서 `?limit=N`은 아래 캐시 키를 N마다 쪼개 무한 증식시킨다.
SHOWCASE_LIMIT = 8
MIN_STORE_COUNT = 10

# 쇼케이스 캐시 — TTL도 Redis도 아니다. 최신 분기를 버전 키로 삼아 분기 적재가
# 들어오면 자연 갱신된다(area_score의 시도 벤치마크 캐시와 같은 방식).
#
# 여기서는 성능 최적화 이상의 역할을 한다: 이 엔드포인트는 **인증 없이** 열리는데
# rate limit이 아직 없다(ROADMAP ③-M1 미착수). 캐시가 없으면 반복 호출이 그대로
# GROUP BY 3개로 증폭된다. 캐시 히트 시 DB 왕복은 버전 확인 1회(8버퍼·0.1ms)뿐이다.
# 키가 없는 단일 슬롯이라 무한 증식이 불가능하다.
_SHOWCASE_CACHE: tuple[tuple[int, int], AreaShowcaseView] | None = None


class AreaRankingInteractor(AreaRankingUseCase):
    """상권 디렉터리 대장 — 차원 + 매출·점포 집계를 상권별로 합치고 파생 지표를 낸다.

    정렬은 하지 않는다. 지표를 다 실어 보내고 정렬·검색은 소비자(프론트)가 한다 —
    1,650행이면 클라이언트 필터가 왕복보다 빠르고, `admin/areas`가 이미 그 선례다.
    """

    def __init__(self, repo: AreaRankingRepositoryPort) -> None:
        self._repo = repo

    async def list_ranking(self, query: AreaRankingQuery) -> AreaRankingView:
        latest = await self._repo.latest_quarter()
        areas = await self._repo.find_areas(
            query.district_name, query.division_code, query.dong_name,
        )
        if latest is None or not areas:
            return AreaRankingView(year_quarter=latest, rows=[], services=[])

        services = [
            ServiceOption(code=r.code, name=r.name)
            for r in await self._repo.list_service_codes(latest)
        ]
        prev = _prev_quarter(latest)
        sales = await self._repo.find_sales([latest, prev], query.service_code)
        stores = await self._repo.find_stores(latest, query.service_code)
        changes = await self._repo.find_change_indicators()

        latest_sales = {s.trdar_code: s.monthly_sales for s in sales if s.year_quarter == latest}
        prev_sales = {s.trdar_code: s.monthly_sales for s in sales if s.year_quarter == prev}
        store_map = {s.trdar_code: s for s in stores}

        rows = []
        for a in areas:
            # 상권변화지표 필터(I-1) — 지표 결측 상권은 어떤 분류 필터에도 잡히지 않는다
            if query.change_indicator and changes.get(a.trdar_code) != query.change_indicator:
                continue
            sale = latest_sales.get(a.trdar_code)
            st = store_map.get(a.trdar_code)
            rows.append(AreaRankingRow(
                trdar_code=a.trdar_code,
                trdar_name=a.trdar_name,
                district_name=a.district_name,
                dong_name=a.dong_name,
                division_code=a.division_code,
                division_name=a.division_name,
                lat=a.lat,
                lng=a.lng,
                monthly_sales=sale,
                store_count=st.store_count if st else None,
                sales_per_store=_per_store(sale, st.store_count if st else None),
                sales_qoq=_qoq(sale, prev_sales.get(a.trdar_code)),
                closure_rate=st.closure_rate if st else None,
                area_size=a.area_size,
                change_indicator_name=changes.get(a.trdar_code),
            ))
        return AreaRankingView(
            year_quarter=latest, rows=rows, services=services,
            dong_rollup=_dong_rollup(rows, prev_sales),
        )

    async def showcase(self) -> AreaShowcaseView:
        global _SHOWCASE_CACHE

        version = await self._repo.quarter_range()
        if version is None:
            # 빈 DB — 캐시하지 않는다(적재가 들어와도 영영 빈 응답이 남는다)
            return AreaShowcaseView(
                year_quarter=None, quarter_from=None, area_count=0,
                min_store_count=MIN_STORE_COUNT, rows=[], division_medians=[],
            )
        if _SHOWCASE_CACHE is not None and _SHOWCASE_CACHE[0] == version:
            return _SHOWCASE_CACHE[1]

        quarter_from, latest = version
        # 전 상권을 그대로 받아 쓴다 — 쇼케이스 전용 쿼리를 새로 파지 않는다.
        ranking = await self.list_ranking(AreaRankingQuery())

        # 점포 1~2개짜리 극단값을 걷어낸다. 하한은 응답에 실어 보내 프론트 카피가
        # 이 숫자를 따로 하드코딩하지 않게 한다.
        eligible = [
            r for r in ranking.rows
            if r.sales_per_store is not None
            and r.store_count is not None
            and r.store_count >= MIN_STORE_COUNT
        ]
        eligible.sort(key=lambda r: r.sales_per_store, reverse=True)

        # 자치구당 1곳 — 이게 없으면 상위 8장 중 6장이 한 자치구의 도매시장으로 채워진다.
        # 지리적으로 흩어지고, 상권유형도 자연히 섞인다.
        seen_districts: set[str] = set()
        rows: list[AreaShowcaseRow] = []
        for r in eligible:
            if r.district_name in seen_districts:
                continue
            seen_districts.add(r.district_name)
            rows.append(AreaShowcaseRow(
                trdar_code=r.trdar_code,
                trdar_name=r.trdar_name,
                district_name=r.district_name,
                division_name=r.division_name,
                sales_per_store=r.sales_per_store,
                store_count=r.store_count,
            ))
            if len(rows) == SHOWCASE_LIMIT:
                break

        view = AreaShowcaseView(
            year_quarter=latest,
            quarter_from=quarter_from,
            area_count=len(ranking.rows),
            min_store_count=MIN_STORE_COUNT,
            rows=rows,
            division_medians=_division_medians(eligible),
        )
        _SHOWCASE_CACHE = (version, view)
        return view


def _dong_rollup(
    rows: list[AreaRankingRow], prev_sales: dict[int, int]
) -> list[DongRollupRow]:
    """행정동 단위 합산(I-3) — 이미 만든 행의 재집계라 추가 쿼리가 없다.

    QoQ는 동 합계로 내되 소속 상권 중 하나라도 직전 분기 결측이면 None —
    커버리지가 다른 두 분기를 나누면 허위 성장률이 된다(정직한 결측 유지).
    """
    acc: dict[tuple[str, str], dict] = {}
    for r in rows:
        if not r.dong_name:
            continue  # 행정동 미매핑 상권 — 어느 동에도 넣을 수 없다
        a = acc.setdefault((r.district_name, r.dong_name), {
            "n": 0, "sales": 0, "sales_any": False,
            "prev": 0, "prev_all": True, "stores": 0, "stores_any": False,
        })
        a["n"] += 1
        if r.monthly_sales is not None:
            a["sales"] += r.monthly_sales
            a["sales_any"] = True
            prev = prev_sales.get(r.trdar_code)
            if prev:
                a["prev"] += prev
            else:
                a["prev_all"] = False
        if r.store_count is not None:
            a["stores"] += r.store_count
            a["stores_any"] = True

    out = []
    for (gu, dong), a in acc.items():
        sales = a["sales"] if a["sales_any"] else None
        stores = a["stores"] if a["stores_any"] else None
        qoq = _qoq(sales, a["prev"]) if a["sales_any"] and a["prev_all"] else None
        out.append(DongRollupRow(
            district_name=gu, dong_name=dong, area_count=a["n"],
            monthly_sales=sales, store_count=stores,
            sales_per_store=_per_store(sales, stores), sales_qoq=qoq,
        ))
    out.sort(key=lambda d: d.monthly_sales or 0, reverse=True)
    return out


def _division_medians(rows: list[AreaRankingRow]) -> list[DivisionMedian]:
    """상권유형별 점포당 매출 중앙값 — 추가 쿼리 없이 이미 받은 행에서 만든다.

    평균이 아니라 중앙값이다. 이 분포는 롱테일이라(골목상권 최대/중앙값 30배)
    평균을 쓰면 상위 카드의 극단값을 설명해야 할 지표가 같이 끌려 올라간다.
    """
    grouped: dict[str, list[int]] = {}
    for r in rows:
        grouped.setdefault(r.division_name, []).append(r.sales_per_store)
    return sorted(
        (
            DivisionMedian(
                division_name=name,
                area_count=len(values),
                median_sales_per_store=round(median(values)),
            )
            for name, values in grouped.items()
        ),
        key=lambda d: d.area_count,
        reverse=True,
    )


def _prev_quarter(year_quarter: int) -> int:
    """20251 → 20244 (연도 경계 처리)."""
    year, q = divmod(year_quarter, 10)
    return (year - 1) * 10 + 4 if q == 1 else year_quarter - 1


def _per_store(sales: int | None, stores: int | None) -> int | None:
    if not sales or not stores:  # 점포 0은 나눗셈 불가이자 의미도 없다
        return None
    return round(sales / stores)


def _qoq(now: int | None, before: int | None) -> float | None:
    if now is None or not before:  # 직전 분기 결측·0이면 변화율을 만들 수 없다
        return None
    return round((now - before) / before * 100, 1)
