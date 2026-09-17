"""비교 판정·표 — 상권/종목 비교의 결론과 표를 코드가 만든다(순수 함수, LLM 없음).

2026-09-17 실대화 289: "길음역과 비교해봐"에 단독 추천, "그래서 어디야"에 제3의 상권, "둘이 비교해줘"에
같은 답 반복. 원인은 비교가 대화 상태가 아니라 매 턴 새 추천이었던 것. 여기서는
  ① 결론이 맨 앞 — 어느 것이 몇 축 중 몇 축 우위인지 수치와 함께 한 줄로 못박는다
  ② 가진 데이터를 전부 표에 싣는다 — 축마다 우위를 표시하고, 못 쓴 데이터는 왜 못 썼는지 적는다
  ③ 우열은 축별 다수결 — 주의·위험 등급 상권은 수치가 앞서도 1순위에 두지 않는다
종목은 '상승 참고 신호 우위'까지만 말한다 — 매수·매도 권유 표현은 쓰지 않는다(유사투자자문업 미신고).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from chat.domain.services.answer_guard import CAUTION_GRADES

# ---------------------------------------------------------------------------
# 공통 — 축별 승자 판정
# ---------------------------------------------------------------------------


def josa(name: str, with_batchim: str, without: str) -> str:
    """한글 받침에 맞는 조사 — 마지막 글자가 한글이 아니면(예: '애플(AAPL)') 괄호 앞 글자로 판단, 그래도 없으면 병기."""
    core = name.split("(")[0].rstrip() or name
    ch = core[-1]
    code = ord(ch)
    if 0xAC00 <= code <= 0xD7A3:
        return f"{name}{with_batchim if (code - 0xAC00) % 28 else without}"
    return f"{name}{with_batchim}({without})"


@dataclass(frozen=True)
class Axis:
    key: str
    label: str
    higher_is_better: bool = True
    fmt: str = "{:,.0f}"
    unit: str = ""
    missing_label: str = "값 없음"


@dataclass
class AxisResult:
    axis: Axis
    values: dict[str, float]      # 항목 이름 → 값(값이 없는 항목은 빠진다)
    winner: str | None            # 동률·비교 불가면 None
    skipped: str = ""             # 비교하지 못한 이유(빈 문자열이면 비교함)
    tied: tuple[str, ...] = ()    # 최선값을 나눠 가진 항목들(2개 이상이면 winner는 None)

    def verdict_text(self) -> str:
        if self.skipped:
            return f"비교 안 함 — {self.skipped}"
        if self.winner is not None:
            return f"{self.winner} 우위 ({self.listing()})"
        if len(self.tied) == len(self.values):
            return f"동률 ({self.listing()})"
        return f"{'·'.join(self.tied)} 공동 우위 ({self.listing()})"

    def listing(self) -> str:
        parts = []
        for name, v in self.values.items():
            parts.append(f"{name} {self.axis.fmt.format(v)}{self.axis.unit}")
        return " vs ".join(parts)


def judge_axes(axes: list[Axis], values_by_item: dict[str, dict[str, float | None]]) -> list[AxisResult]:
    """항목별 값 표에서 축마다 승자를 정한다. 값이 있는 항목이 2개 미만이면 그 축은 비교하지 않는다."""
    results: list[AxisResult] = []
    for axis in axes:
        vals = {name: v[axis.key] for name, v in values_by_item.items() if v.get(axis.key) is not None}
        if len(vals) < 2:
            missing = [name for name in values_by_item if name not in vals]
            results.append(AxisResult(axis, vals, None, skipped=f"{'·'.join(missing)} {axis.missing_label}"))
            continue
        best_v = max(vals.values()) if axis.higher_is_better else min(vals.values())
        tied = [n for n, v in vals.items() if v == best_v]
        results.append(AxisResult(axis, vals, tied[0] if len(tied) == 1 else None, tied=tuple(tied)))
    return results


def tally(results: list[AxisResult], names: list[str]) -> dict[str, list[str]]:
    """항목 이름 → 이긴 축 라벨 목록(입력 순서 유지)."""
    wins = {n: [] for n in names}
    for r in results:
        if r.winner is not None:
            wins[r.winner].append(r.axis.label)
    return wins


# ---------------------------------------------------------------------------
# 상권
# ---------------------------------------------------------------------------

AREA_AXES = [
    Axis("sales_per_store", "점포당 월매출", True, "{:,.0f}", "만원"),
    Axis("closure_rate", "최근 1년 폐업률", False, "{:.1f}", "%"),
    Axis("foot_daily", "일평균 유동인구", True, "{:,.0f}", "명"),
    Axis("score_total", "상권 건강 점수", True, "{:.1f}", "점"),
    Axis("operating_months", "평균 영업 개월", True, "{:.0f}", "개월"),
    Axis("attainment", "손익분기 달성률", True, "{:.0%}", ""),
    Axis("fitness", "입지 적합도", True, "{:.0f}", "점"),
    Axis("vacancy_rate", "공실률", False, "{:.1f}", "%"),
]


@dataclass(frozen=True)
class AreaCompareItem:
    code: int
    name: str
    district: str
    texts: dict[str, str]                      # _format_stats 결과(revenue_text 등) — 표에 그대로 싣는다
    sales_per_store: float | None              # 만원 — 표본 작음(점포 5개 미만)이면 None
    closure_rate: float | None                 # % — 최근 4분기 점포 가중(판정용), 표본 작음·4분기 미만이면 None
    foot_daily: float | None
    operating_months: float | None
    small_sample: bool
    score_total: float | None
    grade: str | None
    components: tuple[tuple[str, str, float, float, float], ...] = ()   # (키, 이름, 점수, 상권값, 서울값)
    trend: str = ""
    insights: tuple[str, ...] = ()
    permit: tuple[int, int, int, int] | None = None                # 개업·폐업·영업중·개월
    rank_sales: tuple[int, int] | None = None                     # (순위, 전체) 점포당 매출
    rank_closure: tuple[int, int] | None = None
    news: tuple[str, ...] = ()
    finance: dict | None = None                                   # rent·bep·attainment·profit·gap·rent_level·vacancy·rent_region
    fitness: dict | None = None                                   # total(0~100)·components[(label,score,weight)]·diagnoses[(tone,msg)]·ticket·similar
    graph: dict | None = None                                     # region_path·siblings·industries·has_service·rivals·articles
    backtest: dict | None = None                                  # 이 등급의 실측(점수 v2 백테스트): n·closure(향후 1년 폐업률)·closure_n·floating
    has_industry_sales: bool = True                               # 이 업종 매출 기록이 있나 — 없으면 1순위 판정에서 뺀다

    def axis_values(self) -> dict[str, float | None]:
        return {
            "sales_per_store": self.sales_per_store,
            "closure_rate": self.closure_rate,
            "foot_daily": self.foot_daily,
            "score_total": self.score_total,
            "operating_months": self.operating_months,
            "attainment": (self.finance or {}).get("attainment"),
            "fitness": (self.fitness or {}).get("total"),
            "vacancy_rate": (self.finance or {}).get("vacancy"),
        }


@dataclass
class AreaVerdict:
    first: str | None                 # 1순위 상권 이름(둘 다 주의·위험이면 None)
    wins: dict[str, list[str]]
    results: list[AxisResult]
    compared: int                     # 비교한 축 수
    caution_note: str                 # 등급 때문에 1순위에서 제외한 설명
    line: str                         # "**결론** …" 한 줄


GRADE_ORDER = ("우수", "양호", "보통", "주의", "위험")


def area_verdict(items: list[AreaCompareItem]) -> AreaVerdict:
    """1순위는 **검증된 점수 v2의 등급**으로만 정한다(2026-09-17 개정).

    예전 규칙은 8축 다수결이었다 — 건강 점수와 그 구성요소(폐업률·영업개월·점포당 매출)를 따로 또 세고,
    예측력이 확인되지 않은 유동인구·입지 적합도가 같은 한 표를 가졌다. 등급 구간은 향후 1년 폐업률이
    단조로 갈리는 것이 백테스트로 확인된 유일한 판정이라(우수 2.0% → 위험 3.7%), 등급이 한 단계 이상 높은
    곳만 1순위로 부르고 같은 등급이면 우열을 가르지 않는다. 나머지 축은 참고 비교로만 보여준다.
    """
    names = [i.name for i in items]
    results = judge_axes(AREA_AXES, {i.name: i.axis_values() for i in items})
    wins = tally(results, names)
    compared = sum(1 for r in results if not r.skipped)
    # 업종 매출이 없는 상권은 등급이 높아도 1순위에서 뺀다 — 등급은 상권 전체 점수라 "이 업종으로 해볼 곳"의 근거가
    # 되지 못한다(2026-09-17 실사용: 커피 매출 기록이 없는 길음시장이 '양호'로 1순위 후보에 올랐다)
    graded = sorted(
        (i for i in items if i.grade in GRADE_ORDER and i.score_total is not None and i.has_industry_sales),
        key=lambda i: (GRADE_ORDER.index(i.grade), -i.score_total),
    )
    no_sales = [i.name for i in items if not i.has_industry_sales]
    ungraded = [i.name for i in items if i not in graded and i.has_industry_sales]
    tail = f" 점수 미산출: {'·'.join(ungraded)}." if ungraded else ""
    if no_sales:
        tail += f" 이 업종 매출 기록 없음(1순위 판정 제외): {'·'.join(no_sales)}."
    scores = " · ".join(f"{i.name} '{i.grade}' {i.score_total:.1f}점" for i in graded)

    first: str | None = None
    caution_note = ""
    if len(graded) < 2:
        line = (f"**결론** 1순위 없음 — 상권 건강 점수(v2)가 있는 곳이 2곳 미만이라 판정하지 않아요.{tail}"
                " 아래 참고 지표로 비교해 보세요.")
    elif graded[0].grade == graded[1].grade:
        same = [i.name for i in items if i in graded and i.grade == graded[0].grade]  # 입력 순서 — 순위처럼 보이지 않게
        line = (f"**결론** 1순위 없음 — {josa('·'.join(same), '은', '는')} 같은 '{graded[0].grade}' 등급이라"
                f" 우열을 가르지 않아요({scores}). 등급 안의 점수 차이는 향후 폐업률 차이로 검증되지 않았어요.{tail}")
        lower = [i for i in graded if i.grade != graded[0].grade]
        if lower:
            line += (f" {josa('·'.join(i.name for i in lower), '은', '는')} 등급이 한 단계 이상 낮아"
                     f"({'·'.join(repr(i.grade) for i in lower).replace(chr(39), '')}) 먼저 고를 곳은 아니에요.")
    else:
        top, runner = graded[0], graded[1]
        first = top.name
        line = (f"**결론** {first} 1순위 — 상권 건강 등급이 '{top.grade}'({top.score_total:.1f}점)로"
                f" 다음인 {runner.name} '{runner.grade}'({runner.score_total:.1f}점)보다 높아요."
                f" 등급은 향후 1년 폐업률로 검증된 점수(v2) 구간이에요({scores}).{tail}")
        if top.grade in CAUTION_GRADES:
            caution_note = f"다만 {josa(first, '은', '는')} '{top.grade}' 등급이라 유의점을 먼저 보세요."
            line += f" {caution_note}"
    return AreaVerdict(first, wins, results, compared, caution_note, line)


# 점수 v2 컴포넌트 실측치 단위 — chat_interactor._SCORE_VALUE_FORMAT과 같은 축(표에서는 짧게)
_COMPONENT_VALUE_FORMAT = {
    "closure_stability": "4분기 폐업률 {:.1f}%",
    "persistence": "{:.0f}개월",
    "sales_level": "{:,.0f}만원",
}


def _cell(text: str | None, fallback: str = "데이터 없음") -> str:
    return text if text and "없음" not in text else fallback


def _mark(name: str, winner: str | None) -> str:
    return "★ " if winner == name else ""


def strengths_block(items: list[AreaCompareItem], results: list[AxisResult]) -> str:
    """상권별 특장점 — 축별 판정을 상권 기준으로 다시 묶는다(2026-09-17 실사용: "각 지역마다 특장점을 이야기 해줘야지").

    강점 = 그 축 최선값(단독·공동), 약점 = 비교 대상 3곳 이상에서 최악값이거나 2곳 비교에서 진 축.
    판정(1순위)과 별개로, 사용자가 곳마다 무엇을 얻고 무엇을 감수하는지 한 줄씩 보게 한다.
    """
    lines = []
    for i in items:
        strong, weak = [], []
        for r in results:
            if r.skipped or i.name not in r.values:
                continue
            vals, axis = r.values, r.axis
            v = vals[i.name]
            value = f"{axis.fmt.format(v)}{axis.unit}"
            n = len(vals)
            worst = min(vals.values()) if axis.higher_is_better else max(vals.values())
            if i.name in r.tied or r.winner == i.name:
                strong.append(f"{axis.label} {value}" + (f"({n}곳 중 1위)" if n >= 3 and len(r.tied) <= 1 else ""))
            elif v == worst:
                tag = "최하" if axis.higher_is_better else "최고"
                weak.append(f"{axis.label} {value}" + (f"({n}곳 중 {tag})" if n >= 3 else ""))
        grade = f" ('{i.grade}' {i.score_total:.1f}점)" if i.grade and i.score_total is not None else " (등급 미산출)"
        parts = [f"강점 — {' · '.join(strong)}" if strong else "강점 — 비교 축에서 앞선 항목 없음"]
        if weak:
            parts.append(f"약점 — {' · '.join(weak)}")
        if i.insights:
            parts.append(f"성격 — {i.insights[0]}")
        if i.fitness and i.fitness.get("diagnoses"):
            bad = next((m for t, m in i.fitness["diagnoses"] if t == "bad"), None)
            if bad:
                parts.append(f"주의 — {bad}")
        lines.append(f"- **{i.name}**{grade}: " + " / ".join(parts))
    return "**상권별 특장점**\n" + "\n".join(lines)


def _startup_cost_line(c: dict) -> str:
    # 항목별 중앙값은 서로 다른 브랜드에서 나와 더해도 합계 중앙값이 되지 않는다("합계 8,036 = … 기타 9,262" 오독, 2026-09-17)
    line = (f"**업종 공통 — 창업비용(공정위 정보공개서 {c['year']}, {c['industry']} 브랜드 중앙값)** 합계 {c['total']:,}만원"
            f" (항목별 중앙값: 가맹금 {c['franchise_fee']:,} · 교육비 {c['education_fee']:,} · 보증금 {c['deposit']:,} · 기타 {c['other_fee']:,}만원"
            " — 브랜드마다 달라 더해도 합계와 같지 않아요). 점포 임대료·인테리어는 별도라 실제 총액은 이보다 커요.")
    if c.get("budget"):
        cap = c["budget"] * 0.7
        line += (f" 예산 {c['budget'] / 10000:,.0f}만원의 70%({cap / 10000:,.0f}만원) 안에 "
                 + ("들어와요." if c["total"] * 10000 <= cap else "안 들어와요."))
    return line


def _quarters(text: str) -> str:
    """추이 문구의 분기 코드(20251)를 읽히는 표기(2025년 1분기)로."""
    return re.sub(r"\b(20\d{2})([1-4])\b", r"\1년 \2분기", text)


def _finance_text(f: dict) -> str:
    parts = []
    if f.get("rent") is not None:
        parts.append(f"월세(추정) {f['rent']:,}만원({f.get('rent_level', '')}{' ' + f['rent_region'] if f.get('rent_region') else ''})")
    if f.get("vacancy") is not None:
        parts.append(f"공실률 {f['vacancy']:.1f}%")
    if f.get("key_money") is not None:
        parts.append(f"권리금 {f['key_money']:,}만원({'입력' if f.get('key_money_note') == '입력' else '가정'})")
    if f.get("bep") is not None:
        parts.append(f"손익분기 월매출 {f['bep']:,}만원")
    if f.get("attainment") is not None:
        parts.append(f"현재 점포당 매출로 손익분기 {f['attainment']:.0%} 달성")
    if f.get("profit") is not None:
        parts.append(f"월 이익(추정) {f['profit']:,}만원")
    if f.get("gap") is not None:
        parts.append(f"부족 자금 {f['gap']:,}만원" if f["gap"] > 0 else "자기자본으로 충당")
    return " · ".join(parts)


def _area_detail_blocks(items: list[AreaCompareItem]) -> list[str]:
    """곳마다 성격·추이·적합도 진단·재무·인허가·기사를 한 단락으로 — 특장점 후속·단일 리포트용."""
    mark = {"good": "○", "warn": "△", "bad": "✕"}
    out = []
    for i in items:
        lines = [f"**{i.name}** ({i.district})"]
        if i.insights:
            lines.append("- 고객·배후 성격: " + " / ".join(i.insights))
        if i.trend:
            lines.append(f"- 추이: {_quarters(i.trend)}")
        if i.permit:
            opened, closed, active, months = i.permit
            lines.append(f"- 인허가 교체(최근 {months}개월): 개업 {opened} · 폐업 {closed} · 영업중 {active}")
        if i.fitness and i.fitness.get("diagnoses"):
            lines.append("- 입지 적합도 진단: " + " / ".join(f"{mark.get(t, '·')} {m}" for t, m in i.fitness["diagnoses"]))
        if i.finance:
            lines.append(f"- 재무: {_finance_text(i.finance)}")
        if i.news:
            lines.append("- 최근 기사: " + " / ".join(i.news))
        if len(lines) > 1:
            out.append("\n".join(lines))
    return out


# 단일 상권 리포트 머리 — 채점기가 이 뒤(코드가 데이터로 쓴 근거 블록)를 모델 서술의 환각 숫자 판정에서 뺀다
REPORT_HEADING = "**상권 리포트 — "


def render_area_report(item: AreaCompareItem, *, service_name: str, quarter_label: str, missing_notes: list[str],
                       startup_cost: dict | None = None,
                       predictiveness: dict[str, tuple[float | None, float | None, int]] | None = None) -> str:
    """단일 상권 리포트 — 비교와 같은 데이터를 한 곳에 대해 판단 순서(수익성 → 안정성 → 수요 → 경쟁 → 비용)로 푼다.

    2026-09-17 실사용: "성수동 카페 상권 어때요?"의 답이 결론 한 줄 + 1문장(168자)이었다. 수치는 전부 코드가 넣는다
    (LLM 서술은 앞 단락의 해석, 이 블록은 근거표). 서울 순위·등급 구성요소·백테스트 실측으로 "그래서 좋은 편인가"를 붙인다.
    """
    t = item.texts
    lines = [f"{REPORT_HEADING}{item.name}** ({item.district} · {service_name} · {quarter_label})"]
    rev = [_cell(t.get("revenue_text"), "")]
    if item.rank_sales:
        rev.append(f"서울 {item.rank_sales[1]:,}곳 중 {item.rank_sales[0]:,}위")
    if t.get("weekday_text") and "없음" not in t["weekday_text"]:
        rev.append(t["weekday_text"])
    if item.small_sample:
        rev.append("점포 5개 미만이라 표본이 작아요")
    lines.append("- **수익성**: " + " · ".join(p for p in rev if p) + (f" (산식: {t['revenue_source']})" if t.get("revenue_source") else ""))

    stab = []
    if item.closure_rate is not None:
        stab.append(f"최근 1년 폐업률 {item.closure_rate:.1f}%" + (f"(서울 낮은 순 {item.rank_closure[0]:,}위/{item.rank_closure[1]:,}곳)" if item.rank_closure else ""))
    if t.get("op_months_text") and "없음" not in t["op_months_text"]:
        stab.append(t["op_months_text"])
    if item.score_total is not None:
        comps = []
        for key, cname, cscore, value, bench in item.components:
            fmt = _COMPONENT_VALUE_FORMAT.get(key, "{:.1f}")
            pred = (predictiveness or {}).get(key)
            rho = f", 예측력 ρ={pred[0]:+.2f}" if pred and pred[0] is not None else ""
            comps.append(f"{cname} {cscore:.0f}점({fmt.format(value)} / 서울 중앙 {fmt.format(bench)}{rho})")
        stab.append(f"상권 건강 {item.score_total:.1f}점 '{item.grade}'" + (f" — {' · '.join(comps)}" if comps else ""))
    if item.backtest and item.backtest.get("closure") is not None:
        stab.append(f"같은 '{item.grade}' 등급 상권의 다음 1년 폐업률 실측 평균 {item.backtest['closure']:.2f}%({item.backtest['closure_n']:,}건)")
    if stab:
        lines.append("- **안정성**: " + " · ".join(stab))

    demand = [x for x in (t.get("foot_text"), f"피크 {t['peak_time']}" if t.get("peak_time") and "없음" not in t["peak_time"] else "",
                          f"유동인구 최다 연령 {t['top_age']}" if t.get("top_age") and "없음" not in t["top_age"] else "",
                          f"상권 변화 '{t['change_text']}'" if t.get("change_text") and "없음" not in t["change_text"] else "")
              if x and "없음" not in x]
    if demand:
        lines.append("- **수요**: " + " · ".join(demand))
    if item.insights:
        lines.append("- **고객·배후 성격**: " + " / ".join(item.insights))

    comp = [x for x in (t.get("store_count_text"), t.get("franchise_text"), t.get("closure_text"), t.get("opening_text")) if x and "없음" not in x]
    if item.permit:
        opened, closed, active, months = item.permit
        comp.append(f"인허가 최근 {months}개월 개업 {opened}·폐업 {closed}·영업중 {active}")
    if item.graph and item.graph.get("rivals") is not None:
        comp.append(f"같은 동 {service_name} 상권 {item.graph['rivals']}곳")
    if comp:
        lines.append("- **경쟁**: " + " · ".join(comp))
    if item.fitness:
        mark = {"good": "○", "warn": "△", "bad": "✕"}
        f = item.fitness
        head = f"{f['total']:.0f}점" if f.get("total") is not None else "산출 불가"
        parts = [f"{label} {score * 100:.0f}점" for label, score, _w in f.get("components", ())]
        if f.get("ticket"):
            parts.append(f"객단가 {f['ticket']:,}원")
        diag = " / ".join(f"{mark.get(tone, '·')} {m}" for tone, m in f.get("diagnoses", ()))
        lines.append(f"- **입지 적합도(업종×상권)**: {head}" + (f" — {' · '.join(parts)}" if parts else "") + (f" · 진단: {diag}" if diag else ""))
    if item.finance:
        lines.append(f"- **재무**: {_finance_text(item.finance)}")
    if item.trend:
        lines.append(f"- **추이**: {_quarters(item.trend)}")
    if item.news:
        lines.append("- **최근 기사**: " + " / ".join(item.news))
    out = ["\n".join(lines)]
    if startup_cost:
        out.append(_startup_cost_line(startup_cost))
    notes = [m for m in missing_notes if not m.startswith("(참고)")]
    if notes:
        out.append("**이 리포트에 못 쓴 데이터**\n" + "\n".join(f"- {m}" for m in notes))
    out.append("다른 동네와 나란히 보려면 \"성수동이랑 연남동 비교해줘\"처럼 물어봐 주세요.")
    return "\n\n".join(out)


def render_area_compare(items: list[AreaCompareItem], v: AreaVerdict, *, service_name: str,
                        quarter_label: str, brief: bool, missing_notes: list[str],
                        startup_cost: dict | None = None,
                        predictiveness: dict[str, tuple[float | None, float | None, int]] | None = None,
                        focus: str = "") -> str:
    """결론 → (등급 고지) → 축별 판정 → 전체 표 → 업종 공통(창업비용) → 상권 성격·추이·진단·기사 → 못 쓴 데이터 → 조작 안내.
    startup_cost: 업종 공통 창업비용(공정위) — 상권마다 같아 열이 아니라 블록. predictiveness: 컴포넌트 키 → (spearman, 상하위 5분위 차, n)."""
    names = [i.name for i in items]
    win_of = {r.axis.key: r.winner for r in v.results}
    out: list[str] = [v.line, strengths_block(items, v.results)]
    if focus == "strengths":
        # "각 지역마다 특장점" 후속 — 같은 전체 표를 다시 내지 않고 곳마다 성격·추이·진단·재무를 풀어 쓴다
        out.extend(_area_detail_blocks(items))
        if startup_cost:
            out.append(_startup_cost_line(startup_cost))
        out.append("축별 판정과 전체 지표 표는 \"자세히 비교해줘\"라고 하면 다시 보여 드려요.")
        return "\n\n".join(out)

    out.append("**참고 지표별 비교** (1순위 판정에는 쓰지 않아요)\n"
               + "\n".join(f"- {r.axis.label}: {r.verdict_text()}" for r in v.results))
    if brief:
        out.append("'자세히 비교해줘'라고 하면 전체 지표 표를 드려요.")
        return "\n\n".join(out)

    head = "| 항목 | " + " | ".join(names) + " |\n|---|" + "---|" * len(names)
    rows: list[tuple[str, list[str]]] = []

    def row(label: str, cells: list[str], axis_key: str | None = None):
        w = win_of.get(axis_key) if axis_key else None
        rows.append((label, [f"{_mark(n, w)}{c}" for n, c in zip(names, cells)]))

    t = [i.texts for i in items]
    row("점포당 월매출", [_cell(x.get("revenue_text")) for x in t], "sales_per_store")
    row("매출 산식", [_cell(x.get("revenue_source"), "-") for x in t])
    row("서울 순위(점포당 매출)", [f"{i.rank_sales[0]:,}위 / {i.rank_sales[1]:,}곳" if i.rank_sales else "순위 없음" for i in items])
    row("주중/주말 매출", [_cell(x.get("weekday_text")) for x in t])
    row("최근 1년 폐업률(4분기 점포 가중)", [f"{i.closure_rate:.1f}%" if i.closure_rate is not None else "산출 불가" for i in items], "closure_rate")
    row("분기 폐업률", [_cell(x.get("closure_text")) for x in t])
    row("서울 순위(폐업률 낮은 순)", [f"{i.rank_closure[0]:,}위 / {i.rank_closure[1]:,}곳" if i.rank_closure else "순위 없음" for i in items])
    row("분기 개업률", [_cell(x.get("opening_text")) for x in t])
    row("점포 수", [_cell(x.get("store_count_text")) for x in t])
    row("프랜차이즈", [_cell(x.get("franchise_text")) for x in t])
    row("동일 업종 경쟁", [_cell(x.get("rival_text")) for x in t])
    row("일평균 유동인구", [_cell(x.get("foot_text")) for x in t], "foot_daily")
    row("유동인구 최다 연령", [_cell(x.get("top_age")) for x in t])
    row("유동인구 피크 시간", [_cell(x.get("peak_time")) for x in t])
    row("상권 변화 유형", [_cell(x.get("change_text")) for x in t])
    row("영업 지속(개월)", [_cell(x.get("op_months_text")) for x in t], "operating_months")
    row("상권 건강 점수(50 = 서울 중앙 상권)", [f"{i.score_total:.1f}점 '{i.grade}'" if i.score_total is not None else "미산출" for i in items], "score_total")
    comp_keys: list[tuple[str, str]] = []
    for i in items:
        for c in i.components:
            if all(c[0] != k for k, _ in comp_keys):
                comp_keys.append((c[0], c[1]))
    for key, cname in comp_keys:
        cells = []
        for i in items:
            c = next((c for c in i.components if c[0] == key), None)
            fmt = _COMPONENT_VALUE_FORMAT.get(key, "{:.1f}")
            cells.append(f"{c[2]:.0f}점 ({fmt.format(c[3])} / 서울 중앙 {fmt.format(c[4])})" if c else "미산출")
        pred = (predictiveness or {}).get(key)
        tag = ""
        if pred is not None and pred[0] is not None:
            tag = f" · 예측력 ρ={pred[0]:+.2f}" + (f", 점수 하위−상위 5분위 폐업률 {pred[1]:+.1f}%p" if pred[1] is not None else "")
        row(f"  └ {cname}{tag}", cells)
    if any(i.backtest for i in items):
        def bt(i: AreaCompareItem) -> str:
            b = i.backtest
            if not b:
                return "등급 없음"
            if b.get("closure") is None:
                return f"'{i.grade}' 등급 {b['n']:,}건: 폐업률 실측 없음(구버전 리포트)"
            return f"'{i.grade}' 등급 {b['closure_n']:,}건 평균 {b['closure']:.2f}%"
        row("이 등급의 다음 1년 폐업률(백테스트 실측)", [bt(i) for i in items])
    if any(i.fitness for i in items):
        f = [i.fitness or {} for i in items]
        row("입지 적합도(업종×상권, 100점)", [f"{x['total']:.0f}점" if x.get("total") is not None else "산출 불가" for x in f], "fitness")
        fit_labels: list[str] = []
        for x in f:
            for label, _s, _w in x.get("components", ()):
                if label not in fit_labels:
                    fit_labels.append(label)
        for label in fit_labels:
            cells = []
            for x in f:
                c = next((c for c in x.get("components", ()) if c[0] == label), None)
                cells.append(f"{c[1] * 100:.0f}점 (가중치 {c[2]:.0%})" if c else "산출 불가")
            row(f"  └ {label}", cells)
        row("객단가(건당 결제액)", [f"{x['ticket']:,}원" if x.get("ticket") else "산출 불가" for x in f])
        row("유사 업종 점포 수", [f"{x['similar']:,}개" if x.get("similar") is not None else "산출 불가" for x in f])
    if any(i.graph for i in items):
        g = [i.graph or {} for i in items]
        row("행정 계층(그래프)", [" → ".join(x.get("region_path", ())) or "연결 없음" for x in g])
        row("같은 동 상권 수(그래프)", [f"{x['siblings']}곳" if x else "연결 없음" for x in g])
        row("영업 업종 수(그래프, 100개 중)", [f"{x['industries']}개" if x else "연결 없음" for x in g])
        row(f"{service_name} 연결", [("있음" if x.get("has_service") else "없음") if x else "연결 없음" for x in g])
        row(f"같은 동 {service_name} 상권 수(그래프 경쟁)", [f"{x['rivals']}곳" if x else "연결 없음" for x in g])
        row("연결된 지역 기사 수(그래프)", [f"{x['articles']}건" if x else "연결 없음" for x in g])
    if any(i.permit for i in items):
        row("인허가 업소 교체", [f"개업 {p[0]} · 폐업 {p[1]} · 영업중 {p[2]} (최근 {p[3]}개월)" if (p := i.permit) else "집계 없음" for i in items])
    if any(i.finance for i in items):
        f = [i.finance or {} for i in items]
        row("월세(추정)", [f"{x['rent']:,}만원 ({x.get('rent_level', '')}{' ' + x['rent_region'] if x.get('rent_region') else ''})" if x.get("rent") is not None else "산출 불가" for x in f])
        row("공실률(R-ONE)", [f"{x['vacancy']:.1f}%" if x.get("vacancy") is not None else "산출 불가" for x in f], "vacancy_rate")
        row("상가 수익률(분기, 소득·자본)", [
            f"소득 {x['income_return']:.2f}% · 자본 {x['capital_return']:+.2f}%"
            if x.get("income_return") is not None and x.get("capital_return") is not None else "산출 불가" for x in f
        ])
        row("권리금", [f"{x['key_money']:,}만원 ({'입력' if x.get('key_money_note') == '입력' else '가정'})"
                       if x.get("key_money") is not None else "산출 불가" for x in f])
        row("손익분기 월매출", [f"{x['bep']:,}만원" if x.get("bep") is not None else "산출 불가" for x in f])
        row("손익분기 달성률", [f"{x['attainment']:.0%}" if x.get("attainment") is not None else "산출 불가" for x in f], "attainment")
        row("월 이익(추정)", [f"{x['profit']:,}만원" if x.get("profit") is not None else "산출 불가" for x in f])
        row("부족 자금", [f"{x['gap']:,}만원" if x.get("gap") is not None else "산출 불가" for x in f])
    table = head + "\n" + "\n".join(f"| {label} | " + " | ".join(cells) + " |" for label, cells in rows)
    out.append(f"**전체 지표** — {service_name}, {quarter_label} 기준 (★ = 그 축 우위)\n{table}")

    if startup_cost:
        out.append(_startup_cost_line(startup_cost))
    key_money_notes = list(dict.fromkeys(
        n for i in items if (n := (i.finance or {}).get("key_money_note")) and n != "입력"
    ))
    if key_money_notes:
        out.append("**권리금 가정** " + " / ".join(key_money_notes) + " — 권리금 없는 자리면 \"권리금 0\"이라고 말해 주세요.")

    extras = []
    for i in items:
        block = []
        if i.insights:
            block.append("상권 성격: " + " / ".join(i.insights))
        if i.trend:
            block.append(i.trend)
        if i.fitness and i.fitness.get("diagnoses"):
            mark = {"good": "○", "warn": "△", "bad": "✕"}
            block.append("적합도 진단: " + " / ".join(f"{mark.get(t, '·')} {m}" for t, m in i.fitness["diagnoses"]))
        if i.news:
            block.append("최근 기사: " + " / ".join(i.news))
        if block:
            extras.append(f"- {i.name}: " + " · ".join(block))
    if extras:
        out.append("**상권 성격·추이·진단·기사**\n" + "\n".join(extras))
    if missing_notes:
        out.append("**이번 비교에 못 쓴 데이터**\n" + "\n".join(f"- {m}" for m in missing_notes))
    out.append("다른 지역을 말하면 이 표에 열을 더하고, \"길음 빼고\"처럼 말하면 뺍니다. 결론만 다시 보려면 \"그래서 어디야\".")
    return "\n\n".join(out)


# ---------------------------------------------------------------------------
# 종목
# ---------------------------------------------------------------------------

STOCK_AXES = [
    Axis("score", "방향 종합 점수", True, "{:+.2f}", ""),
    Axis("edge", "과거 같은 신호 상승 비율 − 평소", True, "{:+.0f}", "%p", missing_label="표본 유의성 미달(n<100 또는 평소와 차이 없음)"),
    Axis("momentum", "12-1 모멘텀", True, "{:+.1%}", ""),
    Axis("obv", "OBV 수급 기울기", True, "{:+.2f}", ""),
    Axis("volume", "거래량(20일 대비)", True, "{:.1f}", "배"),
    Axis("sentiment", "뉴스 감성", True, "{:+.2f}", ""),
    Axis("fundamental", "펀더멘털(긍정−경고)", True, "{:+.0f}", ""),
]


@dataclass(frozen=True)
class StockCompareItem:
    label: str                       # "삼성전자(005930)"
    symbol: str
    unit: str
    price: float
    direction: str
    strength: str
    score: float
    rsi: float
    ma20: float
    ma50: float
    support: float
    resistance: float
    atr_pct: float
    bb_percent_b: float
    volume_ratio: float
    volume_cell: str
    obv_slope: float
    momentum_12_1: float
    reference_up_signal: bool
    sentiment: float
    sentiment_label: str
    poc_text: str = ""
    forecast: dict | None = None     # up_rate·baseline·n·ready·ci_low·ci_high
    fundamentals: tuple[tuple[str, str], ...] = ()   # (tone, text)
    keywords: tuple[str, ...] = ()
    news: tuple[str, ...] = ()
    watch: str | None = None
    board: str | None = None
    paper: str | None = None

    def axis_values(self) -> dict[str, float | None]:
        f = self.forecast or {}
        edge = None
        if f.get("ready") and f.get("up_rate") is not None and f.get("baseline") is not None:
            edge = (f["up_rate"] - f["baseline"]) * 100
        tones = [t for t, _ in self.fundamentals]
        fund = (tones.count("positive") - tones.count("warning")) if tones else None
        return {
            "score": self.score,
            "edge": edge,
            "momentum": self.momentum_12_1,
            "obv": self.obv_slope,
            "volume": self.volume_ratio,
            "sentiment": self.sentiment,
            "fundamental": fund,
        }


@dataclass
class StockVerdict:
    first: str | None
    wins: dict[str, list[str]]
    results: list[AxisResult]
    compared: int
    line: str


_DIR = {"UP": "반등 신호(과매도)", "DOWN": "조정 신호(과열)", "NEUTRAL": "중립"}


def stock_verdict(items: list[StockCompareItem]) -> StockVerdict:
    names = [i.label for i in items]
    results = judge_axes(STOCK_AXES, {i.label: i.axis_values() for i in items})
    wins = tally(results, names)
    compared = sum(1 for r in results if not r.skipped)
    by = {i.label: i for i in items}
    ordered = sorted(names, key=lambda n: (-len(wins[n]), -by[n].score))
    first = ordered[0] if compared and len(wins[ordered[0]]) > 0 else None

    def wins_text(n: str) -> str:
        return " · ".join((f"{r.axis.label} {r.listing()}" if len(names) <= 2 else r.axis.label)
                          for r in results if r.winner == n) or "우위 축 없음"

    if first is None:
        line = f"**결론** {' vs '.join(names)} — 비교한 {compared}축에서 우위가 갈리지 않아요. 우열을 짓지 않습니다."
    else:
        others = [n for n in ordered if n != first]
        rest = "; ".join(f"{josa(n, '은', '는')} {len(wins[n])}축({', '.join(wins[n]) or '없음'})" for n in others)
        dirs = ", ".join(f"{n} {_DIR.get(by[n].direction, by[n].direction)}({by[n].strength})" for n in names)
        line = (f"**결론** 데이터상 {first} 우위 — 비교한 {compared}축 중 {len(wins[first])}축({wins_text(first)})."
                f" {rest}. 지금 신호는 {dirs}. 과거·현재 지표의 대조일 뿐 매수·매도 권유가 아니에요.")
    return StockVerdict(first, wins, results, compared, line)


def _price(v: float, unit: str) -> str:
    return f"{v:,.0f}{unit}" if unit == "원" else f"${v:,.2f}"


def render_stock_compare(items: list[StockCompareItem], v: StockVerdict, *, brief: bool,
                         missing_notes: list[str]) -> str:
    names = [i.label for i in items]
    win_of = {r.axis.key: r.winner for r in v.results}
    out: list[str] = [v.line]
    out.append("**축별 판정**\n" + "\n".join(f"- {r.axis.label}: {r.verdict_text()}" for r in v.results))
    if brief:
        # 거래량 신뢰/의심 판정(C1 골격)은 표를 생략해도 남긴다 — 골든셋 volume_verdict_rate가 결론만 답할 때 떨어졌다
        out.append("**거래량 판정** " + " / ".join(f"{i.label} {i.volume_cell}" for i in items))
        out.append("'자세히 비교해줘'라고 하면 전체 지표 표를 드려요.")
        return "\n\n".join(out)

    head = "| 항목 | " + " | ".join(names) + " |\n|---|" + "---|" * len(names)
    rows: list[tuple[str, list[str]]] = []

    def row(label: str, cells: list[str], axis_key: str | None = None):
        w = win_of.get(axis_key) if axis_key else None
        rows.append((label, [f"{_mark(n, w)}{c}" for n, c in zip(names, cells)]))

    def ma_pos(i: StockCompareItem) -> str:
        a = "위" if i.price > i.ma20 else "아래"
        b = "위" if i.price > i.ma50 else "아래"
        cross = "정배열" if i.ma20 > i.ma50 else "역배열"
        return f"20일 {_price(i.ma20, i.unit)} {a} · 50일 {_price(i.ma50, i.unit)} {b} ({cross})"

    def band(i: StockCompareItem) -> str:
        if not i.resistance > i.support:
            return "구간 없음"
        r = max(0.0, min(1.0, (i.price - i.support) / (i.resistance - i.support)))
        return f"{_price(i.support, i.unit)} ~ {_price(i.resistance, i.unit)} (구간 {r:.0%} 지점)"

    def fc(i: StockCompareItem) -> str:
        f = i.forecast or {}
        if f.get("up_rate") is None or not f.get("n"):
            return "표본 없음"
        base = f" / 평소 {f['baseline']:.0%}" if f.get("baseline") is not None else ""
        sig = "" if f.get("ready") else ", 유의성 미달"
        return f"{f['up_rate']:.0%}{base} (n={f['n']}{sig})"

    def ci(i: StockCompareItem) -> str:
        f = i.forecast or {}
        return f"{f['ci_low']:.0%} ~ {f['ci_high']:.0%}" if f.get("ci_low") is not None else "-"

    row("현재가(지연)", [_price(i.price, i.unit) for i in items])
    row("지금 신호", [f"{_DIR.get(i.direction, i.direction)} ({i.strength})" for i in items])
    row("방향 종합 점수(-1~1)", [f"{i.score:+.2f}" for i in items], "score")
    row("과거 같은 신호 상승 비율", [fc(i) for i in items], "edge")
    row("95% 구간", [ci(i) for i in items])
    row("검증 참고 신호", ["있음" if i.reference_up_signal else "없음" for i in items])
    row("RSI(14)", [f"{i.rsi:.0f}" for i in items])
    row("볼린저 %B", [f"{i.bb_percent_b:.2f}" for i in items])
    row("이동평균 위치", [ma_pos(i) for i in items])
    row("60일 저점~고점", [band(i) for i in items])
    row("거래 밀집 구간", [i.poc_text or "산출 불가" for i in items])
    row("ATR 변동성", [f"{i.atr_pct * 100:.1f}%" for i in items])
    row("거래량(20일 대비)", [i.volume_cell for i in items], "volume")
    row("OBV 수급 기울기", [f"{i.obv_slope:+.2f}" for i in items], "obv")
    row("12-1 모멘텀", [f"{i.momentum_12_1:+.1%}" for i in items], "momentum")
    row("뉴스 감성", [f"{i.sentiment_label} ({i.sentiment:+.2f})" for i in items], "sentiment")
    row("영향 키워드", [", ".join(i.keywords) or "표본 미달" for i in items])
    row("펀더멘털", [" / ".join(t for _, t in i.fundamentals) or "미수집" for i in items], "fundamental")
    row("워치리스트 신호", [i.board or "워치리스트 밖" for i in items])
    row("AI 모의투자", [i.paper or "판단 없음" for i in items])
    table = head + "\n" + "\n".join(f"| {label} | " + " | ".join(cells) + " |" for label, cells in rows)
    out.append(f"**전체 지표** (★ = 그 축 우위)\n{table}")

    extras = []
    for i in items:
        block = []
        if i.watch:
            block.append(i.watch)
        if i.news:
            block.append("최근 기사: " + " / ".join(i.news))
        if block:
            extras.append(f"- {i.label}: " + " · ".join(block))
    if extras:
        out.append("**지켜볼 포인트·기사**\n" + "\n".join(extras))
    if missing_notes:
        out.append("**이번 비교에 못 쓴 데이터**\n" + "\n".join(f"- {m}" for m in missing_notes))
    out.append("다른 종목을 말하면 이 표에 열을 더하고, \"하이닉스 빼고\"처럼 말하면 뺍니다. 결론만 다시 보려면 \"그래서 뭐가 나아\".")
    return "\n\n".join(out)
