"""자유 질의(종목명·티커) → 종목 코드 해석.

한국 종목명은 KRX 상장 목록(FinanceDataReader)으로 6자리 코드에 매핑하고,
그 외는 야후 검색으로 보조한다. 해외 종목의 한국어 이름(예: "테슬라", "샌디스크")은
별칭 사전(_OVERSEAS_ALIASES)으로 해석한다 — 소비자(chat)의 LLM 정규화가
실패해도 여기서 받아주는 안전망이다.
"""
from __future__ import annotations

import asyncio
import logging
import re

import FinanceDataReader as fdr
import yfinance as yf

from stock.app.exceptions import MarketDataUnavailableError

logger = logging.getLogger(__name__)

_KR_CODE_RE = re.compile(r"^\d{6}$")
_US_TICKER_RE = re.compile(r"^[A-Za-z][A-Za-z.\-]{0,5}$")

_krx_names: dict[str, str] | None = None  # 종목명 → 6자리 코드 (프로세스 캐시)

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


def _load_krx_names() -> dict[str, str]:
    global _krx_names
    if _krx_names is None:
        listing = fdr.StockListing("KRX")
        _krx_names = {
            str(row.Name).strip(): str(row.Code)
            for row in listing.itertuples()
            if str(row.Market).startswith(("KOSPI", "KOSDAQ"))
        }
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
