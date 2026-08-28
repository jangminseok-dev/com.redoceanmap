"""답변 후처리 결정론 가드 — 소형 모델이 프롬프트로 지키지 못하는 규칙을 코드가 보장한다.

README "소형 LLM을 믿지 않는다"와 같은 방식이다. 2026-08-28 골든셋 실측에서 절대 규칙
위반 13건이 나왔다 — 컨텍스트에 없는 번호 인용 11건, 책임 고지 누락 2건. 프롬프트에 이미
두 규칙이 다 적혀 있었으므로(`STOCK_ANSWER_PROMPT`) 프롬프트를 더 쓰는 것으로는 못 막는다.

판정 기준은 채점기(`eval_scorer`)와 **같은 정규식**을 쓴다. 둘이 갈라지면 가드를 통과한
답변이 채점에서 떨어진다.
"""
from __future__ import annotations

import re

# 컨텍스트가 번호를 배정하는 유일한 표기 — 인터랙터의 '근거 [n]'과 짝이다
_CONTEXT_CITATION = re.compile(r"근거 \[(\d+)\]")
_ANSWER_CITATION = re.compile(r"\[(\d+)\]")

# eval_scorer._has_disclaimer와 동일 판정(꼬리 150자에 주제어 + 책임어)
_DISCLAIMER_TAIL = 150
_DISCLAIMER_SUBJECT = re.compile(r"(투자|매매)")
_DISCLAIMER_OWNER = re.compile(r"(본인|개인|스스로|책임|신중)")

DISCLAIMER = "투자 판단과 그 결과는 본인 책임입니다."


def allowed_citations(context: str) -> set[int]:
    """컨텍스트가 실제로 배정한 근거 번호. 블록이 생략되면 결번이 생긴다(R4 설계)."""
    return {int(n) for n in _CONTEXT_CITATION.findall(context)}


def strip_dangling_citations(answer: str, allowed: set[int]) -> str:
    """배정되지 않은 번호 인용을 지운다 — 없는 근거를 가리키느니 마커가 없는 편이 낫다.

    마커만 걷어내고 문장은 남긴다(문장을 지우면 근거 있는 서술까지 사라진다).
    """
    def _drop(m: re.Match[str]) -> str:
        return m.group(0) if int(m.group(1)) in allowed else ""

    # 마커 제거로 생긴 " ." 같은 공백을 정리한다
    cleaned = _ANSWER_CITATION.sub(_drop, answer)
    cleaned = re.sub(r"[ \t]+([.,)])", r"\1", cleaned)
    return re.sub(r"[ \t]{2,}", " ", cleaned)


# eval_scorer.volume_verdict_rate와 동일 판정("거래량" + 신뢰|의심)
_VOLUME_VERDICT = re.compile(r"신뢰|의심")
# _volume_text의 급증 경계와 같다 — 거래량이 실제로 늘어야 방향을 "뒷받침"한다고 말한다
_VOLUME_SURGE = 1.5
# 배열이 이 비율 이내로 붙어 있으면 "추세가 뚜렷하지 않다"로 본다(정배열·역배열 미형성)
_TREND_FLAT_RATIO = 0.005


def _trend_is_clear(ma20: float, ma50: float) -> bool:
    if not ma50:
        return False
    return abs(ma20 - ma50) / ma50 > _TREND_FLAT_RATIO


def ensure_volume_verdict(answer: str, *, ma20: float, ma50: float, volume_ratio: float) -> str:
    """거래량이 추세를 뒷받침하는지 판정을 보장한다(C1 골격).

    `STOCK_ANSWER_PROMPT` 2번 규칙과 같은 논리다 — **추세가 뚜렷하지 않으면 판정을 생략**하고,
    배열이 서 있으면 거래량 급증 여부로 신뢰/의심을 가른다. 2026-08-28 답변 압축 뒤 실측
    포함률이 0.70 → 0.40으로 떨어졌다: 프롬프트에 규칙이 있어도 7.8B가 절반은 빠뜨린다.

    **추세 판정은 MA 배열로 한다 — 방향 라벨(direction)이 아니다.** 첫 구현이 direction을
    봤다가 골든셋에서 한 번도 발화하지 않았다(스텁이 전 케이스를 NEUTRAL로 고정한다).
    방향은 감성·임계까지 얹힌 종합 판정이고, 프롬프트가 말하는 "추세"는 배열 그 자체다.
    """
    if not _trend_is_clear(ma20, ma50):
        return answer
    if "거래량" in answer and _VOLUME_VERDICT.search(answer):
        return answer
    if volume_ratio >= _VOLUME_SURGE:
        line = f"거래량은 20일 평균의 {volume_ratio:.1f}배로 늘어 추세를 뒷받침합니다 — 신뢰."
    else:
        line = f"거래량은 20일 평균의 {volume_ratio:.1f}배에 그쳐 추세를 뒷받침하지 못합니다 — 의심."
    return f"{answer.rstrip()}\n{line}"


def ensure_disclaimer(answer: str) -> str:
    """책임 고지가 꼬리에 없으면 붙인다. 있으면 그대로 둔다(중복 고지 방지)."""
    tail = answer[-_DISCLAIMER_TAIL:]
    if _DISCLAIMER_SUBJECT.search(tail) and _DISCLAIMER_OWNER.search(tail):
        return answer
    return f"{answer.rstrip()}\n\n{DISCLAIMER}"
