"""서울 상권 3NF 적재 — 차원 먼저(FK 순서) → 팩트(FK 무결성 필터).

발자국 ERD의 ingest 스크립트 컨벤션. data/raw/seoul/ 의 CSV(cp949)를 읽어
정규화 스키마(차원 5 + 팩트 8)에 적재한다. 기존 COLUMN_MAP을 재사용하되
차원 속성 키(상권명·구분명·업종명 등)는 제거해 팩트에는 FK 코드만 남긴다.

서울 열린데이터광장은 추정매출·점포를 **연도별 파일**로 준다. 같은 팩트의 파일이
여러 개일 수 있어 `frames()`가 파일을 순차로 흘리고, 모든 INSERT는 멱등하다
(`ON CONFLICT DO NOTHING`) — 과거 분기 백필을 몇 번 돌려도 안전하다.

    python scripts/ingest_seoul_3nf.py                                    # 전량
    python scripts/ingest_seoul_3nf.py --facts estimated_sales,store --years 2021-2024
    python scripts/ingest_seoul_3nf.py --facts store --years 2021-2024 --dry-run
"""

import argparse
import math
import re
import sys
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
from sqlalchemy import BigInteger, Integer, create_engine, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))
from core.key.secret_manager import get_secret_manager  # noqa: E402

_secrets = get_secret_manager()

DATA = ROOT / "data" / "raw" / "seoul"
ENC = "cp949"
# 내려받은 CSV의 가운뎃점이 물음표로 깨져 온다 — 파일 안에 실제 '?'(0x3F)가 들어 있고 인코딩 문제가 아니다.
# 열린데이터 API 원본은 정상이다(2026-09-18 대조: 종로·청계 관광특구 · 금호2·3가동 · 종로1·2·3·4가동).
# 한글/숫자 사이의 '?'만 가운뎃점으로 되돌린다 — "어디?" 같은 실제 물음표는 앞뒤 조건에 걸리지 않는다.
_BROKEN_DOT = re.compile(r"(?<=[가-힣0-9])\?(?=[가-힣0-9])")


def clean_name(value):
    return _BROKEN_DOT.sub("·", value) if isinstance(value, str) else value
SIDO_SEOUL = "11"  # 행정표준코드 — 서울특별시

from core.database import Base  # noqa: E402
import market.adapter.outbound.orm.region_orm  # noqa: E402,F401
import market.adapter.outbound.orm.trade_area_division_orm  # noqa: E402,F401
import market.adapter.outbound.orm.service_category_orm  # noqa: E402,F401
import market.adapter.outbound.orm.change_indicator_orm  # noqa: E402,F401
import market.adapter.outbound.orm.trade_area_orm  # noqa: E402,F401
import market.adapter.outbound.orm.estimated_sales_orm  # noqa: E402,F401
import market.adapter.outbound.orm.store_orm  # noqa: E402,F401
import market.adapter.outbound.orm.floating_population_orm  # noqa: E402,F401
import market.adapter.outbound.orm.resident_population_orm  # noqa: E402,F401
import market.adapter.outbound.orm.working_population_orm  # noqa: E402,F401
import market.adapter.outbound.orm.consumption_orm  # noqa: E402,F401
import market.adapter.outbound.orm.apartment_orm  # noqa: E402,F401
import market.adapter.outbound.orm.facility_orm  # noqa: E402,F401
import market.adapter.outbound.orm.commercial_change_orm  # noqa: E402,F401
import market.adapter.outbound.orm.commercial_change_benchmark_orm  # noqa: E402,F401

from market.adapter.outbound.csv.column_maps import (  # noqa: E402
    APARTMENT_COLUMN_MAP,
    COMMERCIAL_CHANGE_COLUMN_MAP,
    CONSUMPTION_COLUMN_MAP,
    ESTIMATED_SALES_COLUMN_MAP,
    FACILITY_COLUMN_MAP,
    FLOATING_POPULATION_COLUMN_MAP,
    RESIDENT_POPULATION_COLUMN_MAP,
    STORE_COLUMN_MAP,
    WORKING_POPULATION_COLUMN_MAP,
)

# market 전용 DB(:5434) 우선 — 미설정 환경은 메인 DB 폴백(런타임 전환과 동일 규칙).
# 괄호 주의: 예전엔 .replace가 폴백 분기에만 묶여 MARKET_DATABASE_URL을 쓸 때
# 드라이버 접두사가 안 붙었다(psycopg2를 찾다 죽음). 두 분기 모두 변환한다.
engine = create_engine(
    (_secrets.get("MARKET_DATABASE_URL") or _secrets.require("DATABASE_URL"))
    .replace("postgresql://", "postgresql+psycopg://")
)
T = Base.metadata.tables

# 팩트에서 제거할 차원 속성(코드→명 이행종속) — 이제 차원 테이블 소유
DIM_KEYS = {
    "trdar_div_code", "trdar_div_name", "trdar_name",
    "service_name", "change_indicator_name",
}


def csv(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA / f"서울시 상권분석서비스({name}).csv", encoding=ENC)


def csv_paths(name: str, years: set[int] | None = None) -> list[Path]:
    """해당 팩트의 CSV 경로 — 기본 파일 + 연도별 파일(`..._2021년.csv`).

    `years`를 주면 파일명 연도로 거른다. 기본 파일(연도 없음)은 최신 연도분이라
    연도 필터가 걸리면 제외된다.
    """
    paths = sorted(DATA.glob(f"서울시 상권분석서비스({name})*.csv"))
    if years is None:
        return paths
    picked = []
    for p in paths:
        m = re.search(r"_(\d{4})년", p.name)
        if m and int(m.group(1)) in years:
            picked.append(p)
    return picked


def frames(name: str, years: set[int] | None = None) -> Iterator[tuple[Path, pd.DataFrame]]:
    """CSV를 파일 단위로 흘린다 — 연도 전체를 concat하지 않아 메모리 상한이 파일 1개다."""
    for path in csv_paths(name, years):
        yield path, pd.read_csv(path, encoding=ENC)


def _code(v) -> str | None:
    return str(int(v)) if pd.notna(v) else None


def clean_records(df: pd.DataFrame, table) -> list[dict]:
    cols = [c for c in df.columns if c in table.columns.keys() and c != "id"]
    df = df[cols]
    int_cols = {c for c in cols if isinstance(table.columns[c].type, (Integer, BigInteger))}
    out = []
    for rec in df.to_dict("records"):
        row = {}
        for k, v in rec.items():
            if v is None or v is pd.NA or (isinstance(v, float) and math.isnan(v)):
                row[k] = None
            elif k in int_cols:
                row[k] = int(v)
            else:
                row[k] = v
        out.append(row)
    return out


def bulk(table, records: list[dict], chunk: int = 5000) -> int:
    """멱등 적재 — 이미 있는 행은 조용히 건너뛴다(`ON CONFLICT DO NOTHING`).

    과거 분기 백필은 차원(PK)·팩트(유니크)를 모두 다시 밟으므로, 순수 INSERT면
    두 번째 실행이 제약 위반으로 전량 롤백된다. 반환값은 **시도 행수**이고
    실제 순증은 호출부가 전후 카운트로 확인한다(정정 재배포는 DELETE 후 재적재).
    """
    if not records:
        return 0
    stmt = pg_insert(table).on_conflict_do_nothing()
    with engine.begin() as con:
        for i in range(0, len(records), chunk):
            con.execute(stmt, records[i:i + chunk])
    return len(records)


def row_count(table) -> int:
    with engine.connect() as con:
        return con.execute(select(func.count()).select_from(table)).scalar_one()


def main(
    facts_filter: set[str] | None = None,
    years: set[int] | None = None,
    dry_run: bool = False,
) -> None:
    def load(label: str, table, records: list[dict]) -> None:
        """차원 적재 — dry-run이면 건수만 보고하고 쓰지 않는다."""
        if dry_run:
            print(f"{label}: dry-run {len(records):,}행 (적재하지 않음)")
        else:
            print(f"{label}:", bulk(table, records))

    ar = csv("영역-상권")
    gu = csv("영역-자치구")

    # 1) 상권구분 차원
    div = ar[["상권_구분_코드", "상권_구분_코드_명"]].drop_duplicates()
    load("trade_area_division", T["trade_area_division"],
         [{"code": c, "name": n} for c, n in div.values])

    # 2) region — 시도(level0, 서울) → 자치구(level1)
    load("region(시도)", T["region"], [{
        "code": SIDO_SEOUL, "name": "서울특별시", "level": 0, "parent_code": None,
        "x_coord": None, "y_coord": None, "area_size": None,
    }])
    gu_recs = [{
        "code": _code(r["자치구_코드"]), "name": clean_name(r["자치구_명"]), "level": 1,
        "parent_code": SIDO_SEOUL,
        "x_coord": int(r["엑스좌표_값"]) if pd.notna(r["엑스좌표_값"]) else None,
        "y_coord": int(r["와이좌표_값"]) if pd.notna(r["와이좌표_값"]) else None,
        "area_size": float(r["영역_면적"]) if pd.notna(r["영역_면적"]) else None,
    } for _, r in gu.iterrows()]
    gu_codes = {r["code"] for r in gu_recs}
    load("region(자치구)", T["region"], gu_recs)

    # 3) region — 행정동(level2, parent=자치구)
    dong = (ar[["행정동_코드", "행정동_코드_명", "자치구_코드"]]
            .dropna(subset=["행정동_코드"]).drop_duplicates(subset=["행정동_코드"]))
    dong_recs = []
    for _, r in dong.iterrows():
        parent = _code(r["자치구_코드"])
        dong_recs.append({
            "code": _code(r["행정동_코드"]), "name": clean_name(r["행정동_코드_명"]), "level": 2,
            "parent_code": parent if parent in gu_codes else None,
            "x_coord": None, "y_coord": None, "area_size": None,
        })
    dong_codes = {r["code"] for r in dong_recs}
    load("region(행정동)", T["region"], dong_recs)

    # 4) service_category (추정매출 + 점포 합집합) — 과거 연도에만 있는 업종 코드가
    #    빠지면 그 행이 FK 필터에서 통째로 탈락하므로, 백필 대상 연도 파일까지 훑는다.
    svc_cols = ["서비스_업종_코드", "서비스_업종_코드_명"]
    svc = pd.concat([
        pd.read_csv(p, encoding=ENC, usecols=svc_cols)
        for name in ("추정매출-상권", "점포-상권")
        for p in csv_paths(name, years)
    ]).drop_duplicates(subset=["서비스_업종_코드"])
    svc_codes = set(svc["서비스_업종_코드"])
    if not dry_run:
        print("service_category:", bulk(T["service_category"],
              [{"code": c, "name": clean_name(n)} for c, n in svc.values]))

    # 5) change_indicator
    chg = csv("상권변화지표-상권")[["상권_변화_지표", "상권_변화_지표_명"]].drop_duplicates(
        subset=["상권_변화_지표"])
    chg_codes = set(chg["상권_변화_지표"])
    load("change_indicator", T["change_indicator"],
         [{"code": c, "name": n} for c, n in chg.values])

    # 6) trade_area (중심 차원)
    ta = ar.drop_duplicates(subset=["상권_코드"])
    ta_recs = []
    for _, r in ta.iterrows():
        rc = _code(r["행정동_코드"])
        ta_recs.append({
            "code": int(r["상권_코드"]), "name": clean_name(r["상권_코드_명"]),
            "division_code": r["상권_구분_코드"],
            "region_code": rc if rc in dong_codes else None,
            "x_coord": int(r["엑스좌표_값"]), "y_coord": int(r["와이좌표_값"]),
            "area_size": float(r["영역_면적"]) if pd.notna(r["영역_면적"]) else None,
        })
    ta_codes = {r["code"] for r in ta_recs}
    load("trade_area", T["trade_area"], ta_recs)

    # --- 팩트 (FK 무결성 필터) ---
    facts = [
        ("추정매출-상권", "estimated_sales", ESTIMATED_SALES_COLUMN_MAP, "service"),
        ("점포-상권", "store", STORE_COLUMN_MAP, "service"),
        ("길단위인구-상권", "floating_population", FLOATING_POPULATION_COLUMN_MAP, None),
        ("상주인구-상권", "resident_population", RESIDENT_POPULATION_COLUMN_MAP, None),
        ("직장인구-상권", "working_population", WORKING_POPULATION_COLUMN_MAP, None),
        ("소비-상권", "consumption", CONSUMPTION_COLUMN_MAP, None),
        ("아파트-상권", "apartment", APARTMENT_COLUMN_MAP, None),
        ("집객시설-상권", "facility", FACILITY_COLUMN_MAP, None),
        ("상권변화지표-상권", "commercial_change", COMMERCIAL_CHANGE_COLUMN_MAP, "change"),
    ]
    for fname, table, cmap, kind in facts:
        if facts_filter and table not in facts_filter:
            continue
        m = {k: v for k, v in cmap.items() if v not in DIM_KEYS}
        before = row_count(T[table])
        for path, raw in frames(fname, years):
            df = raw.rename(columns=m)
            total = len(df)
            df = df[df["trdar_code"].isin(ta_codes)]
            dropped_area = total - len(df)
            dropped_fk = 0
            if kind == "service":
                n0 = len(df)
                df = df[df["service_code"].isin(svc_codes)]
                dropped_fk = n0 - len(df)
            elif kind == "change":
                n0 = len(df)
                df = df[df["change_indicator"].isin(chg_codes)]
                dropped_fk = n0 - len(df)
            quarters = sorted(df["year_quarter"].unique().tolist())
            # FK 탈락은 조용히 사라지면 안 된다 — 과거 연도의 미등록 업종 코드가 여기서 드러난다.
            print(f"  {path.name}: 입력 {total:,} → 상권FK 탈락 {dropped_area:,} / "
                  f"{kind or '-'}FK 탈락 {dropped_fk:,} → 적재 대상 {len(df):,} 분기 {quarters}")
            if not dry_run:
                bulk(T[table], clean_records(df, T[table]))
        if dry_run:
            print(f"{table}: dry-run — 적재하지 않음 (현재 {before:,}행)")
        else:
            after = row_count(T[table])
            print(f"{table}: {before:,} → {after:,} (순증 {after - before:+,})")

    # 7) 시도 벤치마크 — 서울 평균(운영/폐업 개월)은 분기+지역에만 종속이라 별도 테이블
    if not facts_filter or "commercial_change" in facts_filter:
        cc = csv("상권변화지표-상권").rename(columns=COMMERCIAL_CHANGE_COLUMN_MAP)
        bench = cc.drop_duplicates(subset=["year_quarter"])
        load("commercial_change_benchmark", T["commercial_change_benchmark"], [{
            "year_quarter": int(r["year_quarter"]),
            "region_code": SIDO_SEOUL,
            "operating_months_avg": int(r["seoul_operating_months_avg"]),
            "closure_months_avg": int(r["seoul_closure_months_avg"]),
        } for _, r in bench.iterrows()])


def _parse_years(spec: str) -> set[int]:
    """'2021-2024' 또는 '2021,2023' 을 연도 집합으로."""
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = (int(x) for x in part.split("-", 1))
            out.update(range(lo, hi + 1))
        elif part:
            out.add(int(part))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="서울 상권 3NF 적재")
    ap.add_argument("--facts", help="적재할 팩트 테이블명(쉼표 구분). 생략 시 전체")
    ap.add_argument("--years", help="연도 필터 예: 2021-2024. 생략 시 전체 파일")
    ap.add_argument("--dry-run", action="store_true",
                    help="적재 없이 파일별 분기·FK 탈락 건수만 보고")
    args = ap.parse_args()
    main(
        facts_filter={f.strip() for f in args.facts.split(",")} if args.facts else None,
        years=_parse_years(args.years) if args.years else None,
        dry_run=args.dry_run,
    )
