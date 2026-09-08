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
    # 삽입 문장은 수치를 담으므로 근거 마커를 함께 단다 — 마커 없는 수치 문장은 citation
    # 커버리지를 깎는다(골든 재완주 실측: 삽입 문장이 커버리지 하락의 주범이었다).
    # 이 가드는 stock 경로 전용이라 [1](시세·지표)이 항상 배정돼 유령 인용이 아니다.
    if volume_ratio >= _VOLUME_SURGE:
        line = f"거래량은 20일 평균의 {volume_ratio:.1f}배로 늘어 추세를 뒷받침합니다 — 신뢰. [1]"
    else:
        line = f"거래량은 20일 평균의 {volume_ratio:.1f}배에 그쳐 추세를 뒷받침하지 못합니다 — 의심. [1]"
    return f"{answer.rstrip()}\n{line}"


def volume_verdict_cell(*, ma20: float, ma50: float, volume_ratio: float) -> str:
    """비교표 한 칸용 거래량 판정 — `ensure_volume_verdict`와 같은 규칙을 표 셀 문자열로.

    2026-09-08 골든셋 재완주: 비교표 경로(SF06 테슬라·애플)가 거래량 판정 없이 답해
    volume_verdict_rate 1.00 → 0.97로 게이트에 걸렸다. 추세가 서 있지 않으면 배수만 적는다.
    """
    ratio = f"{volume_ratio:.1f}배"
    if not _trend_is_clear(ma20, ma50):
        return f"{ratio}(추세 불명확)"
    return f"{ratio} · {'신뢰' if volume_ratio >= _VOLUME_SURGE else '의심'}"


# 지표 해석 결정론(P4-3, 2026-09-02 4차 실측 S2 t3·S9 t4) — RSI 40.3을 "과매수 영역"으로
# 서술하고 같은 대화에서 과매도↔과매수를 뒤집었다. 경계는 컨텍스트 표기와 같다
# (30↓ 과매도 / 70↑ 과매수, %B는 0↓ 과매도 / 1↑ 과매수).
_RSI_OVERBOUGHT = 70.0
_RSI_OVERSOLD = 30.0
_OVERHEAT_WORD = re.compile(r"과매[수도](?:권|\s?(?:영역|구간|상태))?")


def enforce_overheat_claim(
    answer: str, *, rsi: float | None, bb_percent_b: float | None,
) -> str:
    """원값이 허락하지 않는 과매수/과매도 서술을 실제 구간 표현으로 교정한다.

    문장은 남기고 어휘만 바꾼다(등급 가드와 같은 태도). RSI 또는 볼린저 %B 어느 한쪽이
    극단이면 그 방향 표현은 허용한다 — 두 지표 모두 근거 블록에 있어 둘 다 화자의 근거일
    수 있다.
    """
    if rsi is None:
        return answer
    overbought = rsi >= _RSI_OVERBOUGHT or (bb_percent_b is not None and bb_percent_b >= 1.0)
    oversold = rsi <= _RSI_OVERSOLD or (bb_percent_b is not None and bb_percent_b <= 0.0)

    def _fix(m: re.Match) -> str:
        claimed = m.group(0)
        # 교정 표현에 수치를 넣지 않는다 — 마커 없는 수치 문장이 되어 인용 커버리지를
        # 깎는다(골든 재완주 실측). 원값은 대개 같은 문장의 괄호 원문에 이미 있다.
        if claimed.startswith("과매수"):
            if overbought:
                return claimed
            return "과매도 구간" if oversold else "중립 구간"
        if oversold:
            return claimed
        return "과매수 구간" if overbought else "중립 구간"

    return _OVERHEAT_WORD.sub(_fix, answer)


# 같은 실측(S2 t3): 평균 감성 +0.30을 "주로 악재 관련 기사 다수"로 반전 서술했다.
# 감성을 직접 언급한 문장 안에서만 교정한다 — 뉴스 제목 인용 등 일반 문장은 건드리지 않는다.
_SENT_CLEAR = 0.15  # 영향 키워드 tone 경계(±0.15)와 같은 값


def enforce_sentiment_claim(answer: str, sentiment: float | None) -> str:
    if sentiment is None or abs(sentiment) < _SENT_CLEAR:
        return answer  # 모호 구간은 강제하지 않는다(과교정 방지)
    pieces = _SENTENCE_PIECES.split(answer)
    out = []
    for piece in pieces:
        if piece and "감성" in piece:
            if sentiment >= _SENT_CLEAR:
                piece = piece.replace("부정", "긍정").replace("악재", "호재")
            else:
                piece = piece.replace("긍정", "부정").replace("호재", "악재")
        out.append(piece or "")
    return "".join(out)


def ensure_disclaimer(answer: str) -> str:
    """책임 고지가 꼬리에 없으면 붙인다. 있으면 그대로 둔다(중복 고지 방지)."""
    tail = answer[-_DISCLAIMER_TAIL:]
    if _DISCLAIMER_SUBJECT.search(tail) and _DISCLAIMER_OWNER.search(tail):
        return answer
    return f"{answer.rstrip()}\n\n{DISCLAIMER}"


# 등급 결정론 가드 — 2026-08-31 프로덕션 실측(p04): 총점 44.9 '주의' 상권을 "강력히
# 추천합니다. 유동인구 성장률이 서울 평균을 크게 상회"로 사실 반전 서술했다. 등급 의미론
# (50점=서울 평균)은 프롬프트에 있어도 7.8B가 뒤집는다 — 어휘 차단과 등급 고지를 코드가
# 보장한다. 판정 어휘는 eval_scorer의 grade_caution 규칙과 같다.
CAUTION_GRADES = ("주의", "위험")

# 부사는 어디서 지워도 문장이 성립한다 — 어휘 전체를 걷어낸다("강력한"은 명사 수식이라
# 두고, 뒤의 추천→검토 치환이 "강력한 검토"로 눅인다)
_INTENSIFIER = re.compile(r"(?:강력히|강력하게|적극적으로)\s*")
_RECOMMEND_POLITE = re.compile(r"추천\s*(?:드립니다|드려요)")
_RECOMMEND_PLAIN = re.compile(r"추천\s*(?:합니다|해요)")


def suppress_recommendation(text: str) -> str:
    """'주의'/'위험' 등급 상권 서술의 추천 어휘를 중립(검토)으로 되돌린다.

    문장을 지우지 않는다 — 수치 근거 서술은 남기고 단정 어휘만 바꾼다
    (유령 인용 가드와 같은 태도: 마커만 걷고 문장은 살린다).
    """
    t = _INTENSIFIER.sub("", text)
    t = _RECOMMEND_POLITE.sub("검토해 보시길 바랍니다", t)
    t = _RECOMMEND_PLAIN.sub("검토해볼 만합니다", t)
    return t.replace("추천", "검토")


# 용어 결정론 풀이(I-19, 2026-08-31 실측 q01·q06) — "나스닥도 모른다"는 초보에게
# "12-1 모멘텀 +47.9%, 수급 유출 우위"가 나갔다. 질문에 그 용어가 없으면(초보 추정)
# 첫 등장에 괄호 한 줄 설명을 코드가 붙인다. 질문에 있으면 생략(q04 전문 질의 무풀이).
_GLOSSARY = (
    ("모멘텀", "최근 1년 주가 흐름의 힘"),
    ("수급", "사자·팔자 자금의 흐름"),
    ("%B", "볼린저 밴드 안 현재가 위치 — 0=하단·1=상단"),
    ("ATR", "하루 평균 변동폭"),
    ("정배열", "단기 이동평균이 장기보다 위 — 상승 추세 모양"),
    ("역배열", "단기 이동평균이 장기보다 아래 — 하락 추세 모양"),
)


def attach_glossary(answer: str, prompt: str) -> str:
    """질문자가 쓰지 않은 전문용어의 첫 등장에 괄호 설명을 붙인다(멱등).

    이미 괄호가 붙은 용어("ATR(14)")는 설명이 있는 것으로 보고 건너뛴다 —
    컨텍스트 주입 문장이 이 형태를 쓴다.
    """
    for term, gloss in _GLOSSARY:
        if term in prompt or term not in answer:
            continue
        if f"{term}(" in answer:
            continue
        answer = answer.replace(term, f"{term}({gloss})", 1)
    return answer


# 값 재라벨 금지 가드(I-15) — 컨텍스트가 주지 않은 지표명·거리 판정을 모델이 지어붙인
# 실측 2건(2026-08-31): m1은 폐업률이 '데이터 없음'인데 "높은 폐업률(평균 49개월 내 폐업)"
# 으로 별개 지표(영업 기간)를 재라벨했고, q09는 현재가보다 23% 아래인 매물대를 "근처"라 불렀다.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+|\n+")

NEAR_ATR_MULTIPLE = 2.0
_NEAR_WORD = re.compile(r"근처|부근|인근")
# 구분자를 캡처로 보존해 재조립한다. 소수점(180.10)은 공백이 안 따라와 경계가 아니다.
_SENTENCE_PIECES = re.compile(r"((?<=[.!?…])\s+|\n+)")


def strip_unsupported_metric(reason: str, metric: str) -> str:
    """지표 데이터가 없는데 그 지표명이 등장한 문장을 걷어낸다(I-15 상권판).

    수치만 지우면 라벨("높은 폐업률")이 남아 더 위험하다 — 문장째 지운다.
    '유의할 점' 문장이 지워지면 인터랙터의 _ensure_risk_note가 데이터 기반 문장으로
    다시 채운다(호출 순서가 계약이다).
    """
    kept = [s for s in _SENTENCE_SPLIT.split(reason) if s and metric not in s]
    return " ".join(kept).strip()


def enforce_distance_claim(
    answer: str, *, price: float,
    band_low: float | None, band_high: float | None, atr_value: float,
) -> str:
    """매물대 거리 재라벨 금지(I-15 주식판) — 현재가와 구간 거리가 ATR 2배를 넘으면
    '근처'류 표현을 실제 상대 위치로 교체한다(실측 q09: 23% 아래 구간을 "근처").

    구간을 언급한 문장(매물대·밀집)만 손댄다 — 지지선 등 다른 지표의 '근처'는
    출처가 달라 이 판정으로 재단할 수 없다.
    """
    if not price or band_low is None or band_high is None or atr_value <= 0:
        return answer
    if band_low <= price <= band_high:
        return answer
    edge = band_high if price > band_high else band_low
    if abs(price - edge) <= atr_value * NEAR_ATR_MULTIPLE:
        return answer
    pct = abs(price - edge) / price * 100
    side = "아래" if price > edge else "위"
    replacement = f"(현재가보다 {pct:.0f}% {side})"
    return "".join(
        _NEAR_WORD.sub(replacement, piece)
        if ("매물대" in piece or "밀집" in piece) else piece
        for piece in _SENTENCE_PIECES.split(answer)
    )


def grade_caution_notice(name: str, grade: str, total: float) -> str:
    """등급 고지 한 줄 — 답변 첫 문단에 코드가 삽입한다(모델 서술과 무관하게 항상 정확).

    '주의'(30~45)·'위험'(<30)은 정의상 항상 서울 평균(50점) 미달이다(GRADE_BOUNDS).
    점수 이름을 붙인다 — 2026-09-08 QA P01: 같은 상권이 채팅에선 "종합 44.9점 주의",
    상권 화면에선 "적합도 67점 양호"로 나와 두 점수가 같은 것을 재는 줄 알았다.
    """
    return (
        f"※ {name} 상권은 상권 전체 건강 점수 {total:.1f}점 '{grade}' 등급으로"
        " 서울 평균(50점)에 못 미칩니다(업종 적합도와는 다른 지표예요). 아래 유의점을 먼저 확인하세요."
    )


GRADE_NOTICE_REPEAT = "※ 앞서 안내한 상권 등급 유의점이 이 답에도 그대로 적용돼요."

# 서술-숫자 근거 가드(2026-09-08 QA P02·P03) — 요약문 "37개"·"폐업 4곳"이 카드("60개"·"데이터 없음")와
# 어긋났다. 컨텍스트에 없는 숫자(2자리 이상)가 든 문장은 통째로 걷어낸다. eval_scorer의
# hallucinated_number 규칙과 같은 정규화라 게이트와 런타임이 같은 것을 본다.
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_CITATION_MARK = re.compile(r"\[\d+\]")


def grounded_numbers(text: str) -> set[str]:
    out: set[str] = set()
    for m in _NUM.finditer(text or ""):
        n = m.group().replace(",", "").rstrip(".")
        if "." in n:
            n = n.rstrip("0").rstrip(".")
        if len(n.replace(".", "")) >= 2:
            out.add(n)
    return out


def strip_ungrounded_numbers(text: str, grounded: set[str]) -> str:
    """근거에 없는 숫자가 든 문장을 걷어낸다. 전부 걷히면 원문을 돌려준다(빈 답보다 낫다)."""
    if not text:
        return text
    kept = []
    for sentence in _SENTENCE_SPLIT.split(text):
        if not sentence.strip():
            continue
        nums = grounded_numbers(_CITATION_MARK.sub("", sentence))
        if nums - grounded:
            continue
        kept.append(sentence.strip())
    return " ".join(kept) if kept else text
