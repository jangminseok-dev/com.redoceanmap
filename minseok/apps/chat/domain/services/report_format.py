"""코드가 쓰는 리포트의 표기 규칙 — 상권 리포트(compare)와 종목 리포트(stock_report)가 같이 쓴다. 순수 함수.

2026-09-21 가독성 실측: 채팅 패널은 데스크톱에서도 317px(한 줄 약 23자)인데 리포트는 숫자 여러 개를 `·`와 괄호로
이어 붙인 한 줄(최장 344~755자)이었다 — '안정성' 불릿 하나가 모바일에서 10줄, 숫자 15개. 값을 눈으로 찾을 수 없었다.
규칙: **한 줄에 한 사실**, 값은 굵게, 산식·표본 같은 보조 설명은 기울임(프론트가 작은 회색으로 그린다), 전문 기호는 말로.
프론트 `AnswerBody`는 빈 줄로 단락을 나눠 접으므로 한 섹션 묶음은 빈 줄 없는 중첩 목록으로 쓴다.
"""
from __future__ import annotations

import re

# 문장 안의 첫 "숫자+단위" — 값으로 굵게 한다. 긴 단위가 먼저(만원 > 원). '일'은 뺀다 — "20일 이동평균"·"최근 5일"처럼
# 기간 표시가 값보다 앞에 오는 줄이 많아 엉뚱한 숫자가 굵어진다(값이 뒤에 오는 줄은 호출부가 직접 굵게 한다).
_VALUE = re.compile(r"[+\-−]?\d[\d,]*(?:\.\d+)?\s?(?:억원|만원|만명|개월|%p|원|억|%|점|명|곳|개|위|배|건|회)")
# 끝에 붙은 산식·출처 괄호 — 보조 설명 줄로 뺀다
_TRAILING_NOTE = re.compile(r"\s*\((?P<note>[^()]*(?:÷|산식|추정|기준)[^()]*(?:\([^()]*\)[^()]*)*)\)\s*$")


def bold_value(fact: str) -> str:
    """사실 한 줄의 첫 값(숫자+단위)을 굵게 — 이미 굵은 표기가 있으면 그대로 둔다."""
    if "**" in fact:
        return fact
    return _VALUE.sub(lambda m: f"**{m.group(0)}**", fact, count=1)


class plain(str):
    """자동 굵게를 하지 않을 줄 — 첫 숫자가 값이 아닌 문장("… -10% 이상 하락 30%(평소 24%)")이나 기사 제목."""


def aside(note: str) -> str:
    """보조 설명(산식·표본·출처) — 기울임. 프론트가 작은 회색 글씨로 그린다."""
    return f"_{note.strip()}_"


def split_note(fact: str) -> list[str]:
    """"일평균 12,428명 (분기 총 1,130,942명 ÷ 91일)" → ["일평균 12,428명", "_분기 총 … ÷ 91일_"]."""
    m = _TRAILING_NOTE.search(fact)
    if not m:
        return [fact]
    return [fact[: m.start()].rstrip(), aside(m.group("note"))]


def section(title: str, facts: list[str], *, suffix: str = "", bold: bool = True) -> list[str]:
    """섹션 하나 = 굵은 제목(+ 꼬리말) + 한 사실씩의 하위 목록. 사실이 없으면 섹션 자체를 내지 않는다.
    bold=False는 기사 제목처럼 숫자가 값이 아닌 줄(첫 숫자를 굵게 하면 오히려 어지럽다)."""
    rows = [f for f in facts if f]
    if not rows:
        return []
    return [f"- **{title}**{suffix}",
            *[f"  - {f if not bold or isinstance(f, plain) or f.startswith('_') else bold_value(f)}" for f in rows]]


def predictiveness_word(rho: float | None) -> str:
    """순위상관 ρ를 말로 — 화면에 기호를 내지 않는다. 0.4 이상 강함 · 0.2 이상 보통 · 그 아래 약함."""
    if rho is None:
        return ""
    strength = abs(rho)
    return "예측력 강함" if strength >= 0.4 else "예측력 보통" if strength >= 0.2 else "예측력 약함"


_TREND_POINT = re.compile(
    r"(?P<q>20\d{2}[1-4])(?: 매출 (?P<sales>[\d.,]+)억\(QoQ (?P<sq>[+\-][\d.]+%|-)\))?(?: 유동 (?P<foot>[\d.,]+)만\(QoQ (?P<fq>[+\-][\d.]+%|-)\))?"
)


def _quarter_label(code: str) -> str:
    return f"{code[:4]}년 {code[4]}분기"


def trend_facts(trend: str) -> list[str]:
    """분기 추이 한 줄("20251 매출 137.9억(QoQ -16.0%) 유동 … / …")을 읽히는 요약 사실로 — 6분기를 나열하면 344자였다.

    형식을 못 읽으면 원문에서 기호만 말로 바꿔 한 줄로 돌려준다(열화 동작).
    """
    points = [m for m in _TREND_POINT.finditer(trend) if m.group("sales") or m.group("foot")]
    if not points:
        text = re.sub(r"^-?\s*분기 추이:\s*", "", trend.strip())
        text = re.sub(r"\b(20\d{2})([1-4])\b", r"\1년 \2분기", text).replace("QoQ", "전 분기 대비")
        return [text] if text else []
    facts = []
    sales = [(m.group("q"), float(m.group("sales").replace(",", "")), m.group("sq")) for m in points if m.group("sales")]
    if sales:
        q, v, qoq = sales[-1]
        change = f" — 전 분기 대비 **{qoq}**" if qoq and qoq != "-" else ""
        facts.append(f"{_quarter_label(q)} 매출 **{v:,.1f}억**{change}")
        if len(sales) >= 3:
            hi, lo = max(sales, key=lambda s: s[1]), min(sales, key=lambda s: s[1])
            facts.append(f"최근 {len(sales)}분기 최고 {hi[1]:,.1f}억({_quarter_label(hi[0])}) · 최저 {lo[1]:,.1f}억({_quarter_label(lo[0])})")
    foot = [(m.group("q"), float(m.group("foot").replace(",", "")), m.group("fq")) for m in points if m.group("foot")]
    if foot:
        q, v, qoq = foot[-1]
        change = f" — 전 분기 대비 **{qoq}**" if qoq and qoq != "-" else ""
        facts.append(f"{_quarter_label(q)} 유동인구 **{v:,.1f}만명**{change}")
    return facts
