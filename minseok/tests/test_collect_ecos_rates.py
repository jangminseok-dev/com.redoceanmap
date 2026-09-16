"""collect_ecos_rates 순수 함수 — 항목명 정규화·행 변환(네트워크·DB 없음)."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "collect_ecos_rates", Path(__file__).resolve().parents[1] / "scripts" / "collect_ecos_rates.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def test_각주_번호를_뗀_항목명으로_정규화한다():
    assert _mod.normalize_item("대출평균 1)") == "대출평균"
    assert _mod.normalize_item("한국은행 기준금리") == "한국은행 기준금리"


def test_관심_항목만_행으로_바꾼다():
    raw = [
        {"STAT_CODE": "121Y006", "ITEM_NAME1": "대출평균 1)", "TIME": "202508", "DATA_VALUE": "4.53"},
        {"STAT_CODE": "121Y006", "ITEM_NAME1": "대기업대출", "TIME": "202508", "DATA_VALUE": "4.48"},
        {"STAT_CODE": "722Y001", "ITEM_NAME1": "한국은행 기준금리", "TIME": "202508", "DATA_VALUE": "2.5"},
        {"STAT_CODE": "722Y001", "ITEM_NAME1": "정부대출금금리", "TIME": "202508", "DATA_VALUE": "3.0"},
    ]
    rows = _mod.to_rows(raw)
    assert [(r["stat_code"], r["item_name"], r["year_month"], r["rate"]) for r in rows] == [
        ("121Y006", "대출평균", 202508, 4.53),
        ("722Y001", "한국은행 기준금리", 202508, 2.5),
    ]
