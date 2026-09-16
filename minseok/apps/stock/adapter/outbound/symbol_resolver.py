"""자유 질의(종목명·티커) → 종목 코드 해석.

한국 종목명은 KRX 상장 목록(FinanceDataReader)으로 6자리 코드에 매핑하고,
그 외는 야후 검색으로 보조한다. 해외 종목의 한국어 이름(예: "테슬라", "샌디스크")은
별칭 사전(_OVERSEAS_ALIASES)으로 해석한다 — 소비자(chat)의 LLM 정규화가
실패해도 여기서 받아주는 안전망이다.
"""
from __future__ import annotations

import asyncio
import time
import logging
import re

import FinanceDataReader as fdr
import yfinance as yf

from stock.app.exceptions import MarketDataUnavailableError

logger = logging.getLogger(__name__)

_KR_CODE_RE = re.compile(r"^\d{6}$")
_US_TICKER_RE = re.compile(r"^[A-Za-z][A-Za-z.\-]{0,5}$")

_krx_names: dict[str, str] | None = None  # 종목명 → 6자리 코드 (프로세스 캐시)

# 국내 종목의 국민 별칭(공백 제거형) → KRX 상장명. 상장명이 영문(NAVER·KT 등)이거나
# 한글 발음 표기가 다른 종목만 유지한다 — 부분 일치가 닿는 이름은 여기 넣지 않는다.
_KR_NAME_ALIASES: dict[str, str] = {
    "네이버": "NAVER",
    "케이티": "KT",
    "엘지전자": "LG전자",
    "엘지에너지솔루션": "LG에너지솔루션",
    "포스코": "POSCO홀딩스",
    "에스케이하이닉스": "SK하이닉스",
    # 5차 실측 S7(2026-09-16): 상장명이 "현대자동차"라 "현대차"는 부분 일치가
    # "현대차증권" 하나에만 걸려 001500(7,900원)으로 풀렸다.
    "현대차": "현대자동차",
}

# 해외 종목 한국어명(공백 제거형) → 티커. 한글 질의는 야후 검색을 스킵하므로(아래)
# 여기 없는 해외 종목의 한국어명은 해석 실패가 된다 — 자주 묻는 종목 위주로 유지한다.
_OVERSEAS_ALIASES: dict[str, str] = {
    # 빅테크·반도체
    "애플": "AAPL", "마이크로소프트": "MSFT", "엔비디아": "NVDA",
    "알파벳": "GOOGL", "구글": "GOOGL", "아마존": "AMZN",
    "메타": "META", "페이스북": "META", "테슬라": "TSLA",
    "브로드컴": "AVGO", "오라클": "ORCL", "넷플릭스": "NFLX",
    "인텔": "INTC", "퀄컴": "QCOM", "마이크론": "MU",
    "세일즈포스": "CRM", "어도비": "ADBE", "팔란티어": "PLTR",
    "ARM홀딩스": "ARM", "암홀딩스": "ARM",
    "샌디스크": "SNDK", "웨스턴디지털": "WDC", "슈퍼마이크로": "SMCI",
    "델": "DELL", "시스코": "CSCO", "텍사스인스트루먼트": "TXN",
    "어플라이드머티리얼즈": "AMAT", "램리서치": "LRCX",
    # 헬스케어
    "일라이릴리": "LLY", "노보노디스크": "NVO", "존슨앤존슨": "JNJ",
    "화이자": "PFE", "애브비": "ABBV", "유나이티드헬스": "UNH",
    # 금융
    "버크셔해서웨이": "BRK-B", "버크셔": "BRK-B",
    "JP모건": "JPM", "제이피모건": "JPM", "골드만삭스": "GS",
    "뱅크오브아메리카": "BAC", "비자": "V", "마스터카드": "MA",
    "페이팔": "PYPL", "코인베이스": "COIN",
    # 소비재·에너지·산업
    "코카콜라": "KO", "펩시": "PEP", "맥도날드": "MCD", "스타벅스": "SBUX",
    "나이키": "NKE", "디즈니": "DIS", "월트디즈니": "DIS",
    "코스트코": "COST", "월마트": "WMT", "홈디포": "HD",
    "프록터앤갬블": "PG", "엑슨모빌": "XOM", "셰브론": "CVX",
    "보잉": "BA", "캐터필러": "CAT",
    # 플랫폼·기타
    "우버": "UBER", "에어비앤비": "ABNB", "스포티파이": "SPOT",
    "로블록스": "RBLX", "스노우플레이크": "SNOW", "크라우드스트라이크": "CRWD",
    "리비안": "RIVN", "루시드": "LCID", "알리바바": "BABA",
    "마이크로스트래티지": "MSTR",
}


# KRX 목록을 못 받을 때의 최소 폴백 — 워치리스트 2종목 + 시총 상위 대형주. 정본은 KRX 목록이고
# 이 표는 "삼성전자 질문이 500으로 죽는 것"(2026-09-08 페르소나 QA P04 실측: FinanceDataReader
# KRX 엔드포인트 404)을 막기 위한 안전망이다. 여기 없는 종목은 "찾지 못했습니다"로 열화한다.
_KR_FALLBACK_CODES: dict[str, str] = {
    "삼성전자": "005930", "SK하이닉스": "000660", "LG에너지솔루션": "373220", "삼성바이오로직스": "207940",
    "현대차": "005380", "기아": "000270", "셀트리온": "068270", "NAVER": "035420", "카카오": "035720",
    "POSCO홀딩스": "005490", "LG화학": "051910", "삼성SDI": "006400", "KB금융": "105560", "신한지주": "055550",
    "현대모비스": "012330", "삼성물산": "028260", "한국전력": "015760", "HD현대중공업": "329180",
    "한화에어로스페이스": "012450", "LG전자": "066570", "SK이노베이션": "096770", "크래프톤": "259960",
    "하이브": "352820", "카카오뱅크": "323410", "두산에너빌리티": "034020", "에코프로비엠": "247540",
    "에코프로": "086520", "알테오젠": "196170", "삼성전자우": "005935", "HLB": "028300",
}
_KRX_RETRY_SECONDS = 600.0  # 실패 뒤 이 시간 동안은 재시도하지 않는다(질문마다 404를 때리지 않게)
_krx_failed_at: float | None = None


_KIND_URL = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13"


def _load_from_kind() -> dict[str, str]:
    """KIND(한국거래소 상장공시) 상장법인 목록 — FinanceDataReader의 KRX 엔드포인트가 404가 된 뒤(2026-09-08)
    1순위 소스. 키 없이 받는 HTML 표(회사명·시장구분·종목코드), 코넥스는 뺀다."""
    import io
    import urllib.request

    import pandas as pd

    req = urllib.request.Request(_KIND_URL, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=20).read()
    df = pd.read_html(io.BytesIO(raw), encoding="euc-kr")[0]
    out: dict[str, str] = {}
    for name, market, code in zip(df["회사명"], df["시장구분"], df["종목코드"]):
        if "코넥스" in str(market):
            continue
        code_str = str(code).strip()
        # 종목코드는 대개 6자리 숫자지만 우선주·일부 종목은 영문이 섞인다('0220W0') — 숫자면 0 채움, 아니면 그대로
        out[str(name).strip()] = code_str.zfill(6) if code_str.isdigit() else code_str
    if len(out) < 100:
        raise ValueError(f"KIND 목록이 비정상적으로 짧다: {len(out)}")
    return out


def _load_krx_names() -> dict[str, str]:
    """KRX 상장 목록(종목명 → 코드). KIND → FinanceDataReader → 폴백 표 순. 실패는 10분 뒤 재시도."""
    global _krx_names, _krx_failed_at
    if _krx_names is not None:
        return _krx_names
    if _krx_failed_at is not None and time.monotonic() - _krx_failed_at < _KRX_RETRY_SECONDS:
        return _KR_FALLBACK_CODES
    names: dict[str, str] = {}
    try:
        names = _load_from_kind()
    except Exception as e:
        logger.warning("[symbol-resolver] KIND 상장법인 목록 실패(%s) — FinanceDataReader로 재시도", e)
        try:
            listing = fdr.StockListing("KRX")
            names = {
                str(row.Name).strip(): str(row.Code)
                for row in listing.itertuples()
                if str(row.Market).startswith(("KOSPI", "KOSDAQ"))
            }
        except Exception as e2:  # 네트워크·404·형식 변경 — 종목 질문 전체가 죽으면 안 된다
            _krx_failed_at = time.monotonic()
            logger.warning("[symbol-resolver] KRX 상장 목록 조회 실패(%s) — 폴백 표 %d종목으로 열화", e2, len(_KR_FALLBACK_CODES))
            return _KR_FALLBACK_CODES
    if not names:
        _krx_failed_at = time.monotonic()
        return _KR_FALLBACK_CODES
    _krx_names = names
    logger.info("[symbol-resolver] KRX 상장 목록 캐시: %d종목", len(_krx_names))
    return _krx_names


def _resolve_sync(query: str) -> str:
    q = query.strip()
    if _KR_CODE_RE.match(q):
        return q
    if _US_TICKER_RE.match(q):
        return q.upper()

    compact = q.replace(" ", "")
    # 해외 종목 한국어명은 별칭 사전으로 해석 — KRX 조회(네트워크) 전에 처리한다.
    if compact in _OVERSEAS_ALIASES:
        return _OVERSEAS_ALIASES[compact]
    # 정식 명칭 꼬리 변형("마이크론 테크놀로지" — 3차 실측 P5): 4자 이상 별칭이 머리에
    # 정확히 오면 인정한다. 짧은 별칭은 제외 — "인텔"(2자)을 접두 매칭하면 KRX
    # 인텔리안테크가 INTC로 오매칭된다.
    for alias, ticker in _OVERSEAS_ALIASES.items():
        if len(alias) >= 4 and compact.startswith(alias):
            return ticker

    # 국내 종목 국민 별칭 → KRX 상장명(4차 실측 S5: '네이버'는 상장명이 영문 NAVER라
    # 부분 일치조차 안 걸려 시나리오가 전멸했다). 상장명이 영문·정식명인 종목만 둔다.
    compact = _KR_NAME_ALIASES.get(compact, compact)

    names = _load_krx_names()
    if q in names:
        return names[q]
    if compact in names:
        return names[compact]

    # 부분 일치: "하이닉스" → "SK하이닉스". 유일할 때만 채택, 여러 개면 후보를 알려준다.
    if len(compact) >= 2:
        partial = [name for name in names if compact in name]
        if len(partial) == 1:
            return names[partial[0]]
        if 2 <= len(partial) <= 5:
            raise MarketDataUnavailableError(
                f"'{query}'에 해당하는 종목이 여러 개입니다: {', '.join(sorted(partial))}"
            )

    # 마지막 보조: 야후 검색 (영어 회사명 등).
    # 한글 질의는 제외 — KRX에 없는 한글 이름이 무관한 해외 티커에 오매칭되는 것을 막는다.
    if not _has_hangul(q):
        try:
            quotes = yf.Search(q, max_results=5).quotes
        except Exception:
            quotes = []
        for item in quotes:
            if item.get("quoteType") == "EQUITY" and item.get("symbol"):
                return str(item["symbol"])

    raise MarketDataUnavailableError(f"종목을 찾지 못했습니다: {query}")


def _has_hangul(text: str) -> bool:
    return any("가" <= ch <= "힣" for ch in text)


async def resolve_symbol(query: str) -> str:
    """질의를 종목 코드(한국 6자리 또는 해외 티커)로 해석한다. 동기 I/O는 스레드 분리."""
    return await asyncio.to_thread(_resolve_sync, query)
