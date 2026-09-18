"""서울 CSV 이름 복원 — 내려받은 파일의 가운뎃점이 물음표로 깨져 온다(2026-09-18 실측).

API 원본은 정상이라 표기 정답이 있다: 종로·청계 관광특구 · 종로1·2·3·4가동 · 금호2·3가동.
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "ingest_seoul_3nf", Path(__file__).resolve().parents[1] / "scripts" / "ingest_seoul_3nf.py")


def _clean():
    mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(mod)
    return mod.clean_name


def test_한글_숫자_사이_물음표는_가운뎃점으로_되돌린다():
    clean = _clean()
    assert clean("종로?청계 관광특구") == "종로·청계 관광특구"
    assert clean("금호2?3가동") == "금호2·3가동"
    assert clean("종로1?2?3?4가동") == "종로1·2·3·4가동"   # 연속 물음표도 한 번에


def test_진짜_물음표와_문자열_아닌_값은_건드리지_않는다():
    clean = _clean()
    assert clean("여기가 어디? 상권") == "여기가 어디? 상권"
    assert clean("A?B") == "A?B"          # 한글·숫자 사이가 아니면 그대로
    assert clean(None) is None and clean(3001494) == 3001494
