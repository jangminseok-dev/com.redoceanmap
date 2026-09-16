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
