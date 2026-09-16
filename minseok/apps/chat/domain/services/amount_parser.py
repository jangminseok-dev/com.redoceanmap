"""한국어 금액·라벨 파서 — 결정론. LLM 추출을 쓰지 않는다(추출 오류 = 계산 오류).

parse_budget_krw·fmt_won은 chat_interactor에서 옮겨 왔다(동작 동일). parse_labeled_amounts는
"자기자본 1억, 보증금 5천에 월세 300"을 재무 엔진 입력으로 바꾼다. 월세·임대료의 단위 없는 숫자는
만원(관용)이다.
"""
from __future__ import annotations

import re

PYEONG_TO_SQM = 3.3058

_BUDGET_RE = re.compile(r"(\d+(?:\.\d+)?)\s*억(?:\s*(\d+)\s*(천만?|만))?|(\d+(?:,\d{3})*)\s*(천만|만)\s*원?")
# 5천 = 천만원 단위 관용, 단 "천만"(이미 다른 대안)과 "천원"(소액)은 제외
_CHEON_RE = re.compile(r"(\d+)\s*천(?!\s*(?:만|원))")
_AMOUNT = r"(\d+(?:\.\d+)?)\s*억(?:\s*(\d+)\s*(천만?|만))?|(\d+(?:,\d{3})*)\s*(천만|만)\s*원?|(\d+)\s*천(?!\s*(?:만|원))|(\d{2,4})(?![\d,.]|\s*(?:억|천|만|평|㎡|명|%|개|년|월|일|시))"
_LABELS: tuple[tuple[str, str], ...] = (
    ("equity", r"자기\s*자본|자본금|내\s*돈|가진\s*돈|보유\s*자금|수중에"),
    ("deposit", r"보증금"),
    ("monthly_rent", r"월세|임대료|월\s*임대"),
    ("key_money", r"권리금"),
    ("startup_cost", r"인테리어|설비|시설비"),
    ("desired_loan", r"대출"),
)
_LABELED = {
    key: re.compile(rf"(?:{words})\s*(?:은|는|이|가|을|를|으로|로|도|:)?\s*(?:{_AMOUNT})")
    for key, words in _LABELS
}
_PYEONG_RE = re.compile(r"(\d+(?:\.\d+)?)\s*평")
_SQM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:㎡|m2|제곱미터)")
_HEADCOUNT_RE = re.compile(r"(?:직원|알바|아르바이트|종업원)\s*(\d+)\s*명|(\d+)\s*명\s*(?:직원|알바|고용|쓰)")


def fmt_won(amount: float) -> str:
    """1억 2,000만원 · 8,036만원 — 만원 단위, 억은 앞에 뗀다."""
    man = int(round(amount / 10_000))
    if man >= 10_000:
        eok, rest = divmod(man, 10_000)
        return f"{eok}억원" if rest == 0 else f"{eok}억 {rest:,}만원"
    return f"{man:,}만원"


def parse_budget_krw(text: str) -> int | None:
    """"1억 2천", "8천만원", "5000만원", "1.5억" → 원. 못 읽으면 None(기존 예산 경로와 동일)."""
    m = _BUDGET_RE.search(text)
    if not m:
        return None
    if m.group(1):
        won = float(m.group(1)) * 100_000_000
        if m.group(2):
            won += int(m.group(2)) * (10_000_000 if m.group(3).startswith("천") else 10_000)
        return int(won)
    n = int(m.group(4).replace(",", ""))
    return n * (10_000_000 if m.group(5) == "천만" else 10_000)


def parse_won(text: str) -> int | None:
    """parse_budget_krw + "5천"(천만원 단위) 표기."""
    won = parse_budget_krw(text)
    if won is not None:
        return won
    m = _CHEON_RE.search(text)
    return int(m.group(1)) * 10_000_000 if m else None


def _amount_from_match(m: re.Match, bare_unit: int) -> int | None:
    if m.group(1):
        tail = int(m.group(2)) * (10_000_000 if m.group(3).startswith("천") else 10_000) if m.group(2) else 0
        return int(float(m.group(1)) * 100_000_000 + tail)
    if m.group(4):
        return int(m.group(4).replace(",", "")) * (10_000_000 if m.group(5) == "천만" else 10_000)
    if m.group(6):
        return int(m.group(6)) * 10_000_000
    if m.group(7):
        return int(m.group(7)) * bare_unit
    return None


def solo_amount(text: str) -> int | None:
    """라벨(자기자본·보증금·월세·권리금·인테리어·대출)에 붙은 금액 구간을 지운 뒤 남은 첫 금액 — 예산/자기자본 후보."""
    residual = text
    for pattern in _LABELED.values():
        residual = pattern.sub(" ", residual)
    return parse_won(residual)


def parse_labeled_amounts(text: str) -> dict[str, int | float]:
    """라벨이 붙은 금액·면적·인원만 뽑는다. 라벨 없는 단독 금액은 예산 경로(parse_budget_krw)가 맡는다."""
    out: dict[str, int | float] = {}
    for key, pattern in _LABELED.items():
        m = pattern.search(text)
        if not m:
            continue
        bare_unit = 10_000 if key in ("monthly_rent",) else 0
        amount = _amount_from_match(m, bare_unit)
        if amount:
            out[key] = amount
    if (m := _PYEONG_RE.search(text)):
        out["area_sqm"] = round(float(m.group(1)) * PYEONG_TO_SQM, 1)
    elif (m := _SQM_RE.search(text)):
        out["area_sqm"] = float(m.group(1))
    if (m := _HEADCOUNT_RE.search(text)):
        out["headcount"] = int(m.group(1) or m.group(2))
    return out
