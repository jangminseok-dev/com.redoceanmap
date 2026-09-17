"""결론 정답 게이트 — 답변의 결론이 **데이터상 맞는지** 스냅샷에서 독립적으로 다시 계산해 채점한다. LLM 불필요.

품질 게이트(test_quality_gate)는 형식·금지 표현·환각 숫자를 본다. 결론이 틀려도(1순위를 잘못 골라도, 위험 등급을
성격 순위에 올려도) 형식만 맞으면 통과했다(2026-09-17 점검). 여기서는 결정론 경로의 결론을 채점 코드와 **다른 경로**
— 스냅샷 원값에서 직접 — 로 다시 구해 대조한다. 판정 코드(compare·trait_ranking)를 import하지 않는 것이 원칙이다
(같은 코드로 채점하면 같은 버그가 통과한다). 상수(컷 기준)만 공유한다.

1. 비교(market_compare): 점수가 있는 상권이 2곳 이상이고 최고 등급이 유일하면 "X 1순위", 아니면 "1순위 없음"
2. 성격형·조건 랭킹: 줄마다 등급·1년 폐업률이 스냅샷과 같고 위험 등급이 없으며, 단일 인구·시설 지표면 1위 값이 최댓값
3. phase2 결론: "X부터 보세요"의 X가 최종 추천 1순위이고, 인용한 등급이 스냅샷 등급과 같다
4. 결론-본문 모순(본문이 결론과 다른 상권을 추천): 건수 비증가(모델 확률 결함 — 환각 숫자와 같은 회귀 규칙)
"""
from __future__ import annotations

import asyncio
import json
import re

import pytest

from chat.domain.services import trait_ranking
from chat.tests.eval.golden import BASELINE_PATH, TRACE_PATH, load_cases, load_traces
from chat.tests.eval.snapshot_stubs import SnapshotMarket, synthetic_score

_GRADES = ("우수", "양호", "보통", "주의", "위험")
_RANK_LINE = re.compile(r"^\d+\. (?P<name>.+?) \((?P<gu>\S+) (?P<dong>.+?)\) — (?P<desc>.+?) · 등급 (?P<grade>산출 불가|\S+)"
                        r"(?: · 1년 폐업률 (?P<closure>[\d.]+)%)?$")
_PHASE2_HEAD = re.compile(r"^\*\*결론\*\* .+? 기준으로는 (?P<name>.+?)부터 보세요")
_PHASE2_GRADE = re.compile(r"상권 건강 [\d.]+점 '(?P<grade>\S+?)'")
_SINGLE_METRICS = {   # 단일 인구·시설 지표 — 라벨 → 스냅샷 원값(독립 계산)
    "직장인구": lambda r: r.working_pop,
    "일평균 유동인구": lambda r: r.floating_pop / 91 if r.floating_pop is not None else None,
    "밤(21~06시) 일평균 유동인구": lambda r: r.night_floating_pop / 91 if r.night_floating_pop is not None else None,
    "대학": lambda r: r.university_count,
    "지하철역": lambda r: r.subway_station_count,
}


def _load():
    if not TRACE_PATH.exists():
        pytest.skip("trace.jsonl 없음 — 러너(test_eval_runner.py, -m ollama) 먼저 실행")
    cases = {c.case_id: c for c in load_cases()}
    return cases, load_traces(), SnapshotMarket()


def _grade_of(code: int) -> str | None:
    score = synthetic_score(code)
    return score.grade if score else None


def test_비교_결론은_등급이_한_단계_이상_높은_곳만_1순위다():
    cases, traces, market = _load()
    by_name = {a.trdar_name: a.trdar_code for a in market.area_map.values()}
    checked = 0
    for t in traces:
        if cases.get(t.case_id) is None or cases[t.case_id].category != "market_compare" or t.error:
            continue
        head = t.answer_text.split("\n", 1)[0]
        assert head.startswith("**결론**"), f"{t.case_id}: 결론이 첫 줄이 아니다 — {head[:80]}"
        section = t.answer_text.split("**참고 지표별 비교**", 1)[-1].split("\n\n", 1)[0]
        names = [n for n in by_name if f"{n} " in section or f"{n})" in section]
        assert len(names) >= 2, f"{t.case_id}: 비교 대상 상권을 답변에서 찾지 못했다 — {names}"
        graded = {n: g for n in names if (g := _grade_of(by_name[n])) is not None}
        best = min((_GRADES.index(g) for g in graded.values()), default=None)
        leaders = [n for n, g in graded.items() if best is not None and _GRADES.index(g) == best]
        if len(graded) >= 2 and len(leaders) == 1:
            assert f"{leaders[0]} 1순위" in head, f"{t.case_id}: 정답 1순위 {leaders[0]}({graded}) — 답: {head[:120]}"
        else:
            assert "1순위 없음" in head, f"{t.case_id}: 1순위를 가를 수 없는데({graded}) 답: {head[:120]}"
        checked += 1
    assert checked, "market_compare 케이스가 트레이스에 없다 — 러너 재실행 필요"


def test_성격형_조건_랭킹은_등급_폐업률이_데이터와_같고_위험_등급이_없다():
    cases, traces, market = _load()
    area_map = market.area_map
    ranking = {r.trdar_code: r for r in asyncio.run(market.get_area_ranking())}
    traits = asyncio.run(market.get_area_traits())
    checked = 0
    for t in traces:
        if not t.answer_text.startswith("서울 상권을 '"):
            continue
        rows = [m for line in t.answer_text.split("\n") if (m := _RANK_LINE.match(line))]
        numbered = [line for line in t.answer_text.split("\n") if re.match(r"^\d+\. ", line)]
        stated = int(re.search(r"상위 (\d+)곳", t.answer_text).group(1))
        # 형식이 깨진 줄을 조용히 건너뛰면 채점이 비어도 통과한다 — 번호 줄 전부가 파싱돼야 한다
        assert len(rows) == len(numbered) == stated, f"{t.case_id}: 상위 {stated}곳인데 파싱 {len(rows)}줄/번호 {len(numbered)}줄"
        assert [int(line.split(".", 1)[0]) for line in numbered] == list(range(1, stated + 1)), f"{t.case_id}: 번호 순서가 어긋났다"
        label = t.answer_text.split("'", 2)[1]
        listed = []
        for m in rows:
            codes = [c for c, a in area_map.items()
                     if a.trdar_name == m["name"] and a.district_name == m["gu"]]
            assert len(codes) == 1, f"{t.case_id}: 상권 '{m['name']}'을 스냅샷에서 특정하지 못했다"
            code = codes[0]
            listed.append(code)
            expected = _grade_of(code) or "산출 불가"
            assert m["grade"] == expected, f"{t.case_id}: {m['name']} 등급 {m['grade']} ≠ 데이터 {expected}"
            assert m["grade"] != "위험", f"{t.case_id}: 위험 등급 {m['name']}이 성격 순위에 올랐다"
            if m["closure"] is not None:
                assert float(m["closure"]) == pytest.approx(ranking[code].closure_rate, abs=0.05)
        metric = _SINGLE_METRICS.get(label)
        if metric is not None:
            cap = re.search(r"1년 폐업률 서울 중앙값 ([\d.]+)% 이하", t.answer_text)   # "폐업률 낮은"이 함께면 중앙값 이하만
            eligible = [r for r in traits if r.area_store_count >= trait_ranking.MIN_AREA_STORES
                        and metric(r) is not None and _grade_of(r.trdar_code) != "위험"
                        and (cap is None or (r.trdar_code in ranking and ranking[r.trdar_code].closure_rate is not None
                                             and ranking[r.trdar_code].closure_rate <= float(cap.group(1))))]
            top = max(metric(r) for r in eligible)
            values = [metric(next(r for r in traits if r.trdar_code == c)) for c in listed]
            assert values[0] == top, f"{t.case_id}: '{label}' 1위 값 {values[0]} ≠ 최댓값 {top}"
            assert values == sorted(values, reverse=True), f"{t.case_id}: '{label}' 값이 내림차순이 아니다 {values}"
        checked += 1
    assert checked, "성격형·조건 랭킹 답변이 트레이스에 없다 — 러너 재실행 필요"


def test_phase2_결론의_상권과_등급은_최종_추천과_데이터가_같다():
    _, traces, market = _load()
    area_map = market.area_map
    for t in traces:
        m = _PHASE2_HEAD.match(t.answer_text)
        if not m or not t.recommendation_codes:
            continue
        top = area_map[t.recommendation_codes[0]]
        assert m["name"] == top.trdar_name, f"{t.case_id}: 결론 {m['name']} ≠ 최종 추천 1순위 {top.trdar_name}"
        g = _PHASE2_GRADE.search(t.answer_text.split("\n", 1)[0])
        if g:
            assert g["grade"] == _grade_of(top.trdar_code), f"{t.case_id}: 결론 등급 {g['grade']} ≠ 데이터"


def _contradictions(traces, market) -> list[str]:
    """본문 추천 문장이 결론 상권이 아닌 **다른 스냅샷 상권**을 가리키는 답 — 결론과 본문이 서로 다른 곳을 민다."""
    names = sorted({a.trdar_name for a in market.area_map.values()}, key=len, reverse=True)
    out = []
    for t in traces:
        m = _PHASE2_HEAD.match(t.answer_text)
        if not m or "\n" not in t.answer_text:
            continue
        head_stem = re.sub(r"\(.*?\)", "", m["name"]).strip()
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", t.answer_text.split("\n", 1)[1]):
            if "추천" not in sentence:
                continue
            for n in names:
                stem = re.sub(r"\(.*?\)", "", n).strip()
                if len(stem) >= 3 and stem in sentence and stem not in head_stem and head_stem not in stem:
                    out.append(f"{t.case_id}: 결론 {m['name']} vs 본문 추천 {n}")
                    break
    return out


def test_결론과_본문이_다른_상권을_추천하는_답은_늘지_않는다():
    _, traces, market = _load()
    found = _contradictions(traces, market)
    print(f"\n[oracle] 결론-본문 모순 {len(found)}건 {found}")
    if not BASELINE_PATH.exists():
        pytest.skip("baseline.json 없음 — 품질 게이트가 먼저 기록한다")
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    if "conclusion_contradiction_count" not in baseline:
        baseline["conclusion_contradiction_count"] = len(found)
        BASELINE_PATH.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[oracle] baseline에 결론-본문 모순 건수 최초 기록")
        return
    assert len(found) <= baseline["conclusion_contradiction_count"], (
        f"회귀: 결론-본문 모순 {baseline['conclusion_contradiction_count']}건 → {len(found)}건 ({found})"
    )
