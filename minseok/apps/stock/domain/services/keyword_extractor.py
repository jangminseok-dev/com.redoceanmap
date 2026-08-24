"""주가 영향 키워드 추출(B2) — 결정론, LLM 미사용.

최근 헤드라인의 단어 빈도(문서 빈도)로 "요즘 이 종목 뉴스를 지배하는 말"을 뽑는다.
씽크풀 AI픽워드 대응 축이되, 예측이 아니라 **관측 요약**이다(문장 생성 없음 — 같은
입력이면 항상 같은 결과, bookmark_alert_composer와 같은 신뢰성 원칙).

한계(의도된 v1): 형태소 분석이 아니다 — 대표 조사 1자를 떼는 휴리스틱만 쓴다.
전 코퍼스 IDF 대신 **과빈도 컷(MAX_DF_RATIO)**으로 회사명·상용구를 걸러낸다
(코퍼스 횡단 통계는 조회 비용 대비 이득이 없어 후속 판단).
순수 함수 — 표준 라이브러리만(도메인 순수성).
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

MIN_DOCS = 5        # 헤드라인 표본 하한 — 두세 건짜리 빈도는 잡음이다(빈 리스트 반환)
MIN_COUNT = 2       # 1회 등장 토큰은 키워드가 아니다
MAX_DF_RATIO = 0.7  # 헤드라인 70% 이상에 등장 = 회사명·상용구 — 변별력 0이라 제외
SENTIMENT_TONE_MIN = 0.15  # 동반 감성 평균이 이 이상 기울 때만 호재/악재 방향을 붙인다

# 종목 무관 뉴스 상용구 — 어떤 종목이든 헤드라인에 흔한 말은 "영향 키워드"가 아니다
_STOPWORDS = frozenset({
    "뉴스", "기자", "단독", "속보", "종합", "포토", "영상", "인터뷰",
    "오늘", "내일", "어제", "올해", "작년", "지난", "최근", "이번", "지난해",
    "주가", "주식", "증시", "시장", "종목", "특징주", "테마주",
    "코스피", "코스닥", "나스닥", "뉴욕증시",
    "상승", "하락", "급등", "급락", "강세", "약세", "반등", "돌파", "마감", "개장",
    "전망", "분석", "발표", "공시", "관련", "대비", "기록", "이유", "주목", "기대",
    "투자", "매수", "매도", "목표가", "증권", "리포트", "증권가",
    "억원", "조원", "만원", "달러", "거래일", "분기", "실적발표",
    "대한", "위한", "통해", "함께", "따라", "대해", "속에", "가운데", "어디까지",
})
_PARTICLES = "이가을를은는의에로도와과"  # 토큰 끝 조사 1자 제거 휴리스틱


@dataclass(frozen=True)
class HeadlineSample:
    """헤드라인 1건 — 제목 + LLM 감성 라벨(있으면)."""

    title: str
    sentiment: float | None
    published_at: datetime | None


@dataclass(frozen=True)
class KeywordInsight:
    """영향 키워드 1개 — 빈도·동반 감성·근거 헤드라인."""

    keyword: str
    count: int                    # 포함 헤드라인 수(문서 빈도)
    sentiment_avg: float | None   # 포함 헤드라인 라벨 평균 — 라벨이 하나도 없으면 None
    sample_title: str             # 최신 근거 헤드라인 — R4 근거 배지의 앵커


def _tokens(title: str) -> set[str]:
    out: set[str] = set()
    for tok in re.findall(r"[가-힣]{2,}|[A-Za-z]{2,}", title):
        tok = tok.lower() if tok.isascii() else tok
        if len(tok) >= 3 and tok[-1] in _PARTICLES:
            tok = tok[:-1]  # "실적은"→"실적" — 형태소 분석이 아닌 대표 조사 1자 컷
        if len(tok) >= 2 and tok not in _STOPWORDS:
            out.add(tok)
    return out


def extract_keywords(samples: list[HeadlineSample], limit: int = 5) -> list[KeywordInsight]:
    """헤드라인 표본 → 영향 키워드 Top-N. 표본 미달이면 빈 리스트(침묵이 정직)."""
    docs = [(_tokens(s.title), s) for s in samples if s.title.strip()]
    n = len(docs)
    if n < MIN_DOCS:
        return []
    df = Counter(tok for toks, _ in docs for tok in toks)

    scored: list[tuple[float, int, str, float | None, str]] = []
    for tok, count in df.items():
        if count < MIN_COUNT or count / n > MAX_DF_RATIO:
            continue
        hosts = [s for toks, s in docs if tok in toks]
        sentiments = [s.sentiment for s in hosts if s.sentiment is not None]
        s_avg = round(sum(sentiments) / len(sentiments), 2) if sentiments else None
        # 감성이 기울어진 키워드가 같은 빈도의 중립 키워드보다 "영향" 축에 가깝다
        weight = count * (1.0 + (abs(s_avg) if s_avg is not None else 0.0))
        sample = max(
            hosts,
            key=lambda s: (s.published_at is not None, s.published_at or datetime.min),
        ).title
        scored.append((weight, count, tok, s_avg, sample))

    scored.sort(key=lambda x: (-x[0], -x[1], x[2]))  # 동률은 토큰 사전순 — 결정론 고정
    return [
        KeywordInsight(keyword=tok, count=count, sentiment_avg=s_avg, sample_title=sample)
        for _, count, tok, s_avg, sample in scored[:limit]
    ]
