"""채팅 품질 채점기 — 골든셋 케이스 × 실행 트레이스 → 결정론 지표.

LLM-as-judge를 쓰지 않는다(단일 모델 정책상 7.8B가 자기 답을 심판하는 순환이 된다).
전 지표가 규칙 기반이라 같은 트레이스는 언제 채점해도 같은 결과가 나온다.

지표
- intent_accuracy / intent_confusion : phase0 4분류 정확도·혼동행렬
- stock_query_accuracy               : 종목 질의 추출(허용 목록 대조)
- phase0_parse_failure_rate          : 의도 JSON 파싱 실패(→market 폴백) 비율
- nonseoul_guard_rate                : 서울 외 지역 결정론 차단 성공률(기대 100%)
- region_hit_rate                    : 지역 명시 질문의 추천 상권 적중률
- phase1_guard_activation_rate       : phase1 원답과 최종 추천이 다른(가드 보정) 비율
- inherit_rate / inherit_focus_rate  : 멀티턴 승계율(하나라도 이어받음) / 집중률(그것만 답함)
- volume_verdict_rate                : 주식 답변의 거래량 신뢰/의심 판정 포함률(C1 골격 준수)
- risk_mention_rate                  : 상권 추천 이유의 "유의할 점" 포함률(C2 리스크 의무 준수)
- citation_coverage                  : 수치 주장 문장 중 인용 마커([n]) 포함 비율(R4 출처 인용)
- violations                         : 절대 규칙 위반(환각 숫자·금지 표현·고지 누락·입지 창작·
                                       유령 인용 dangling_citation — 컨텍스트에 없는 근거 번호)
- latency_p50/p95_ms                 : phase별 지연
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass

from chat.domain.value_objects.eval_trace import CaseTrace, EvalCase, LlmCall

# 답변을 만든 마지막 생성 호출 — 환각 숫자 판정의 대조 원본
_GENERATIVE_PHASES = ("phase2", "stock_answer", "market_news_answer")

# 금지 표현(stock·market_news 답변) — 매매 지시·확률 단정
_FORBIDDEN_PATTERNS = (
    r"매수하세요", r"매도하세요", r"매수를 추천", r"매도를 추천",
    r"무조건", r"확실히\s*(오릅|상승|하락)", r"100\s*% ", r"\d+\s*%의?\s*확률",
)

# 책임 고지 판정 — 문구를 열거하지 않고 답변 **말미의 구조**를 본다.
# 모델은 같은 뜻을 매번 다르게 쓴다("본인 책임" · "본인의 판단에 따라" · "개인의 신중한 판단").
# 문구 열거로 가면 변형마다 오탐이 새로 생겨 끝나지 않는다 — 2026-08-05에 28건을 잡고
# 관용구를 넓혔더니 다음 실행에서 또 다른 표현 1건이 걸렸다.
# 말미 안에 '투자·매매' 주어와 '본인·개인·책임' 귀속어가 함께 있으면 고지로 본다.
_DISCLAIMER_TAIL = 150
_DISCLAIMER_SUBJECT = re.compile(r"(투자|매매)")
_DISCLAIMER_OWNER = re.compile(r"(본인|개인|스스로|책임|신중)")


def _has_disclaimer(answer: str) -> bool:
    tail = answer[-_DISCLAIMER_TAIL:]
    return bool(_DISCLAIMER_SUBJECT.search(tail) and _DISCLAIMER_OWNER.search(tail))


# 답변 잘림 — 모델이 문장 중간에 조기 종료한 경우(2026-08-05 MW09: 143자, 쉼표 뒤 중단.
# 같은 단계 p50은 437자였고 토큰 상한 설정은 없다 — 설정으로 막을 수 없는 확률적 결함).
# 절대 규칙이 아니라 **건수 비증가** 회귀로 건다(환각 숫자와 같은 취급).
# general은 외부 Gemini 답변이고 평가에서는 스텁이라 대상에서 뺀다.
_ANSWERED_INTENTS = ("stock", "market_news", "market")
_SENTENCE_END = ".!?…"
_TRAILING_DECOR = " \t\n*_)]\"'`"  # 마크다운 강조·괄호 닫힘은 문장 끝 판정에서 벗겨낸다


def _is_truncated(answer: str) -> bool:
    s = (answer or "").rstrip(_TRAILING_DECOR)
    return bool(s) and s[-1] not in _SENTENCE_END

# 금지 입지 서술(market 답변) — 컨텍스트에 없는 교통·입지 창작(PHASE2_PROMPT 금지 규칙)
_LOCATION_CLAIM_TOKENS = ("호선", "환승", "관문")

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")

# 출처 인용(R4) — 컨텍스트의 근거 번호 표기('근거 [n]', chat_interactor가 단일 정의처)와
# 답변의 인용 마커([n]). phase2(market)는 마커 미도입이라 대상이 아니다(기사 근거가
# 프론트 카드로 노출되지 않아 앵커가 성립하지 않는다 — ROADMAP R4 판정).
_CITED_PHASES = ("stock_answer", "market_news_answer")
_SOURCE_NUM = re.compile(r"근거 \[(\d+)\]")
_MARKER_NUM = re.compile(r"\[(\d+)\]")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+|\n+")
_LEADING_MARKERS = re.compile(r"^\s*((?:\[\d+\]\s*)+)")


def _sentences_with_markers(text: str) -> list[str]:
    """문장 분할 — 문장 첫머리로 밀린 마커는 앞 문장에 귀속시킨다.

    모델이 마커를 마침표 뒤에 쓰면("…입니다. [1]") 단순 분할로는 다음 문장 소유가 되어
    커버리지가 이중으로 틀린다(앞 문장은 미커버, 뒤 문장은 무임 커버).
    """
    out: list[str] = []
    for part in _SENTENCE_SPLIT.split(text or ""):
        if not part.strip():
            continue
        lead = _LEADING_MARKERS.match(part)
        if lead and out:
            out[-1] += lead.group(1)
            part = part[lead.end():]
        if part.strip():
            out.append(part)
    return out


@dataclass(frozen=True)
class RuleViolation:
    case_id: str
    # hallucinated_number | forbidden_phrase | missing_disclaimer | location_claim
    # | truncated_answer | dangling_citation
    rule: str
    detail: str


@dataclass(frozen=True)
class EvalReport:
    total: int
    errored: tuple[str, ...]
    intent_accuracy: float
    intent_confusion: dict[str, dict[str, int]]
    stock_query_accuracy: float | None
    phase0_parse_failure_rate: float
    nonseoul_guard_rate: float | None
    region_hit_rate: float | None
    phase1_guard_activation_rate: float | None
    inherit_rate: float | None        # 직전 추천을 하나라도 이어받았나(교집합)
    inherit_focus_rate: float | None  # 이어받은 것만으로 답했나(부분집합)
    volume_verdict_rate: float | None  # 주식 답변의 거래량 '신뢰/의심' 판정 포함률
    risk_mention_rate: float | None    # 상권 추천 전체 이유에 "유의" 문장 포함률
    citation_coverage: float | None    # 수치 주장 문장 중 인용 마커 포함 비율(마커 도입 경로만)
    violations: tuple[RuleViolation, ...]
    latency_p50_ms: dict[str, float]
    latency_p95_ms: dict[str, float]


def _parse_json(raw: str) -> dict:
    """chat_interactor._parse_llm_json과 같은 관용 파서.

    도메인은 app을 import할 수 없어(계층 방향) 소형 복제를 둔다 —
    파싱 성공/실패 판정 기준이 인터랙터와 같아야 폴백률이 실측이 된다.
    """
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    text = match.group() if match else raw
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return json.loads(text)


def _stem(name: str) -> str:
    """지명 어간 — chat_interactor._place_stem과 같은 규칙(계층 방향상 소형 복제)."""
    match = re.match(r"^[가-힣]+", name or "")
    stem = match.group() if match else ""
    while len(stem) > 2 and stem[-1] in "구동가로읍면리":
        stem = stem[:-1]
    return stem


def _numbers(text: str) -> set[str]:
    """숫자 토큰 정규화 집합 — 콤마·무의미한 소수 0 제거, 10 미만(한 자리)은 잡음이라 제외.

    소수부를 안 지우면 컨텍스트의 `48,400.00`과 답변의 `48,400`이 다른 숫자로 잡힌다.
    2026-08-05 실측에서 환각 의심 63건 중 56건(89%)이 이 형식 차이였다 — 지표가 아니라
    잡음을 세고 있었다. 소수점이 있을 때만 잘라낸다(정수 `100`의 0을 지우면 안 된다).
    """
    out: set[str] = set()
    for m in _NUM.finditer(text or ""):
        n = m.group().replace(",", "").rstrip(".")
        if "." in n:
            n = n.rstrip("0").rstrip(".")
        if len(n.replace(".", "")) >= 2:
            out.add(n)
    return out


def _rate(hits: int, total: int) -> float | None:
    return None if total == 0 else hits / total


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))
    return ordered[idx]


def _call_of(trace: CaseTrace, phase: str) -> LlmCall | None:
    for call in trace.calls:
        if call.phase == phase:
            return call
    return None


def _generative_call(trace: CaseTrace) -> LlmCall | None:
    for call in reversed(trace.calls):
        if call.phase in _GENERATIVE_PHASES:
            return call
    return None


def score(cases: list[EvalCase], traces: list[CaseTrace]) -> EvalReport:
    by_id = {t.case_id: t for t in traces}
    paired = [(c, by_id.get(c.case_id)) for c in cases]
    errored = tuple(
        c.case_id for c, t in paired if t is None or t.error is not None
    )
    scored = [(c, t) for c, t in paired if t is not None and t.error is None]

    # --- 의도 분류 ---
    confusion: dict[str, dict[str, int]] = {}
    intent_hits = 0
    for c, t in scored:
        row = confusion.setdefault(c.expected_intent, {})
        row[t.final_intent] = row.get(t.final_intent, 0) + 1
        if t.final_intent == c.expected_intent:
            intent_hits += 1
    intent_accuracy = _rate(intent_hits, len(scored)) or 0.0

    # --- 종목 질의 추출 ---
    stock_cases = [(c, t) for c, t in scored if c.category.startswith("stock")]
    query_hits = sum(
        1 for c, t in stock_cases
        if t.stock_query.strip().casefold()
        in {q.casefold() for q in c.accepted_queries}
    )
    stock_query_accuracy = _rate(query_hits, len(stock_cases))

    # --- phase0 파싱 실패(→market 폴백) ---
    phase0_traces = [t for _, t in scored if _call_of(t, "phase0")]
    parse_failures = 0
    for t in phase0_traces:
        try:
            _parse_json(_call_of(t, "phase0").response)
        except Exception:
            parse_failures += 1
    phase0_parse_failure_rate = _rate(parse_failures, len(phase0_traces)) or 0.0

    # --- 서울 외 지역 결정론 가드 ---
    nonseoul = [(c, t) for c, t in scored if c.category == "market_nonseoul"]
    nonseoul_ok = sum(
        1 for _, t in nonseoul
        if _call_of(t, "phase1") is None and "준비 중" in t.answer_text
    )
    nonseoul_guard_rate = _rate(nonseoul_ok, len(nonseoul))

    # --- 지역 명시 질문 상권 적중 ---
    region_cases = [(c, t) for c, t in scored if c.category == "market_region"]
    region_hits = sum(
        1 for c, t in region_cases
        if c.region and _stem(c.region)
        and any(_stem(c.region) in label for label in t.recommendation_labels)
    )
    region_hit_rate = _rate(region_hits, len(region_cases))

    # --- phase1 결정론 가드 발동(원답 ≠ 최종) ---
    guarded_pool = [
        t for _, t in scored
        if t.final_intent == "market" and _call_of(t, "phase1") is not None
    ]
    guard_fired = sum(
        1 for t in guarded_pool
        if set(t.phase1_raw_codes) != set(t.recommendation_codes)
    )
    phase1_guard_activation_rate = _rate(guard_fired, len(guarded_pool))

    # --- 멀티턴 승계 — 두 단계로 잰다(2026-08-05 이원화) ---
    # 부분집합 단일 기준은 "이어받고 이웃을 추가"한 케이스까지 실패로 세어 실측 0%가 나왔다
    # (첫 baseline에서 10건 중 5건이 실제로는 시딩 상권을 포함). 승계율은 "이어받긴 했나",
    # 집중률은 ""그 중에서"라고 물었는데 그것만으로 답했나"를 따로 본다.
    multiturn = [(c, t) for c, t in scored if c.category == "multiturn"]
    inherited = sum(
        1 for _, t in multiturn
        if set(t.recommendation_codes) & set(t.seeded_history_codes)
    )
    focused = sum(
        1 for _, t in multiturn
        if t.recommendation_codes
        and set(t.recommendation_codes) <= set(t.seeded_history_codes)
    )
    inherit_rate = _rate(inherited, len(multiturn))
    inherit_focus_rate = _rate(focused, len(multiturn))

    # --- 서술 골격 준수율 (C 골격의 감시 지표 — 규칙은 감시와 함께 태어난다) ---
    # 프롬프트가 판정 어휘('신뢰'/'의심')와 표기("유의할 점")를 의무화하므로 정규식으로 잰다.
    stock_answers = [t for _, t in scored if t.final_intent == "stock" and t.answer_text]
    volume_verdicts = sum(
        1 for t in stock_answers
        if "거래량" in t.answer_text and re.search(r"신뢰|의심", t.answer_text)
    )
    volume_verdict_rate = _rate(volume_verdicts, len(stock_answers))

    market_recs = [t for _, t in scored
                   if t.final_intent == "market" and t.recommendation_reasons]
    risk_mentions = sum(
        1 for t in market_recs
        if all("유의" in reason for reason in t.recommendation_reasons)
    )
    risk_mention_rate = _rate(risk_mentions, len(market_recs))

    # --- 출처 인용(R4) — 커버리지 + 유령 인용 ---
    citation_pool = 0
    citation_covered = 0
    violations: list[RuleViolation] = []
    for c, t in scored:
        gen = _generative_call(t)
        if gen is None or gen.phase not in _CITED_PHASES or not t.answer_text:
            continue
        sources = {int(n) for n in _SOURCE_NUM.findall(gen.prompt)}
        # 유령 인용 — 컨텍스트가 표시하지 않은 근거 번호를 지어낸 것(새 환각 유형, 절대 규칙)
        marker_nums = {int(n) for n in _MARKER_NUM.findall(t.answer_text)}
        for n in sorted(marker_nums - sources):
            violations.append(RuleViolation(c.case_id, "dangling_citation", f"[{n}]"))
        if not sources:
            continue  # 마커 도입 전 트레이스 — 커버리지 표본에서 제외
        for sentence in _sentences_with_markers(t.answer_text):
            # 마커 자체의 숫자([12])가 문장을 '수치 주장'으로 만들지 않게 벗겨내고 센다
            if not _numbers(_MARKER_NUM.sub("", sentence)):
                continue
            citation_pool += 1
            if _MARKER_NUM.search(sentence):
                citation_covered += 1
    citation_coverage = _rate(citation_covered, citation_pool)

    # --- 절대 규칙 위반 ---
    for c, t in scored:
        # 잘린 답변에는 고지 유무를 물을 수 없다 — 끊긴 뒤에 올 문장을 없다고 셀 수는 없다.
        # 잘림으로 따로 세고 고지 판정에서는 면제한다(같은 결함을 두 번 세지 않는다).
        truncated = t.final_intent in _ANSWERED_INTENTS and _is_truncated(t.answer_text)
        if truncated:
            violations.append(
                RuleViolation(c.case_id, "truncated_answer", t.answer_text.rstrip()[-20:])
            )
        if t.final_intent in ("stock", "market_news"):
            for pattern in _FORBIDDEN_PATTERNS:
                m = re.search(pattern, t.answer_text)
                if m:
                    violations.append(RuleViolation(c.case_id, "forbidden_phrase", m.group()))
            if (t.recommendation_codes == () and t.answer_text
                    and not truncated and not _has_disclaimer(t.answer_text)):
                violations.append(RuleViolation(c.case_id, "missing_disclaimer", "책임 고지 없음"))
        if t.final_intent == "market" and t.recommendation_codes:
            market_text = t.answer_text + " " + " ".join(t.recommendation_reasons)
            for token in _LOCATION_CLAIM_TOKENS:
                if token in market_text:
                    violations.append(RuleViolation(c.case_id, "location_claim", token))
        gen = _generative_call(t)
        if gen is not None:
            answer = t.answer_text + " " + " ".join(t.recommendation_reasons)
            grounded = _numbers(gen.prompt) | _numbers(c.prompt)
            # 반올림 동치 — 컨텍스트가 182.36을 주면 모델은 182로 되받는다(2026-08-05 실측
            # SU08). 소수 원값이 있는 숫자의 정수 반올림형은 근거 있는 숫자로 인정한다.
            grounded |= {str(round(float(n))) for n in grounded if "." in n}
            # 퍼센트 동치 — 컨텍스트의 비율 0.9(배)를 모델이 "90%"로 되받는다(같은 날
            # SK13·SK15 실측). 1 미만 소수에 한해 ×100형을 근거로 인정한다.
            grounded |= {
                str(round(float(n) * 100)) for n in grounded
                if "." in n and 0 < float(n) < 1
            }
            for n in sorted(_numbers(answer) - grounded):
                violations.append(RuleViolation(c.case_id, "hallucinated_number", n))

    # --- 지연 ---
    by_phase: dict[str, list[float]] = {}
    for _, t in scored:
        for call in t.calls:
            by_phase.setdefault(call.phase, []).append(call.latency_ms)
    latency_p50 = {p: round(_percentile(v, 0.50), 1) for p, v in by_phase.items()}
    latency_p95 = {p: round(_percentile(v, 0.95), 1) for p, v in by_phase.items()}

    return EvalReport(
        total=len(cases),
        errored=errored,
        intent_accuracy=intent_accuracy,
        intent_confusion=confusion,
        stock_query_accuracy=stock_query_accuracy,
        phase0_parse_failure_rate=phase0_parse_failure_rate,
        nonseoul_guard_rate=nonseoul_guard_rate,
        region_hit_rate=region_hit_rate,
        phase1_guard_activation_rate=phase1_guard_activation_rate,
        inherit_rate=inherit_rate,
        inherit_focus_rate=inherit_focus_rate,
        volume_verdict_rate=volume_verdict_rate,
        risk_mention_rate=risk_mention_rate,
        citation_coverage=citation_coverage,
        violations=tuple(violations),
        latency_p50_ms=latency_p50,
        latency_p95_ms=latency_p95,
    )
