"""collect_rone_rent 순수 함수 — 분기 코드 변환·임대료/공실률 병합(네트워크·DB 없음)."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "collect_rone_rent", Path(__file__).resolve().parents[1] / "scripts" / "collect_rone_rent.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def test_분기_코드는_연도와_분기를_붙인다():
    assert _mod.parse_quarter("202403") == 20243
    assert _mod.parse_quarter("202601") == 20261


def _row(cls_id, fullnm, val, quarter="202602"):
    return {"WRTTIME_IDTFR_ID": quarter, "CLS_ID": cls_id, "CLS_FULLNM": fullnm, "DTA_VAL": val}


def test_임대료와_공실률을_같은_키로_병합하고_서울만_남긴다():
    rent = [_row("520059", "서울>기타>혜화동", "60.03"), _row("510003", "서울>도심", "74.11"),
            _row("500002", "서울", "52.8"), _row("600001", "부산>기타>서면", "30.0")]
    vacancy = [_row("520059", "서울>기타>혜화동", "2.13")]
    rows = _mod.merge_rows("small", rent, vacancy)
    by_cls = {r["cls_id"]: r for r in rows}
    assert set(by_cls) == {"520059", "510003", "500002"}
    assert by_cls["520059"]["rent_per_sqm_krw"] == 60_030  # 천원/㎡ → 원/㎡
    assert by_cls["520059"]["vacancy_rate"] == 2.13
    assert by_cls["520059"]["level"] == 2 and by_cls["520059"]["region_name"] == "혜화동"
    assert by_cls["510003"]["level"] == 1 and by_cls["510003"]["vacancy_rate"] is None
    assert by_cls["500002"]["level"] == 0 and by_cls["500002"]["region_name"] == "서울"
    assert all(r["year_quarter"] == 20262 and r["building_type"] == "small" for r in rows)


def test_수익률_세_항목을_같은_키에_열로_붙인다():
    rent = [_row("520037", "서울>기타>뚝섬", "64.98")]
    returns = [{**_row("520037", "서울>기타>뚝섬", "0.327"), "ITM_NM": "소득수익률"},
               {**_row("520037", "서울>기타>뚝섬", "2.97"), "ITM_NM": "자본수익률"},
               {**_row("520037", "서울>기타>뚝섬", "3.297"), "ITM_NM": "투자수익률"},
               {**_row("999999", "서울>기타>없는곳", "1.0"), "ITM_NM": "소득수익률"}]  # 임대료 행이 없으면 버린다
    (row,) = _mod.merge_rows("small", rent, [], returns)
    assert (row["income_return"], row["capital_return"], row["investment_return"]) == (0.327, 2.97, 3.297)


def test_권리금은_서울만_업종·연도별로_모으고_만원을_원으로():
    def km(year, grp, cls, item, val):
        return {"WRTTIME_IDTFR_ID": year, "GRP_NM": grp, "CLS_NM": cls, "ITM_NM": item, "DTA_VAL": val}
    raw = [km("2025", "서울", "숙박 및 음식점업", "권리금 유 비율", "79.1"),
           km("2025", "서울", "숙박 및 음식점업", "권리금 수준_중위수", "4367.07"),
           km("2025", "서울", "전체 ", "권리금 수준_평균", "4914.9"),
           km("2025", "부산", "숙박 및 음식점업", "권리금 유 비율", "60.0")]
    rows = {r["industry_group"]: r for r in _mod.key_money_rows(raw)}
    assert set(rows) == {"숙박 및 음식점업", "전체"}  # "전체 " 공백 정리, 부산 제외
    food = rows["숙박 및 음식점업"]
    assert food["key_money_ratio"] == 79.1 and food["median_krw"] == 43_670_700 and food["year"] == 2025
    assert rows["전체"]["avg_krw"] == 49_149_000
