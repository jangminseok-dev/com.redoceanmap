"""미국 저평가 스크리닝 + 질문 수요 편입 — 워치리스트 auto 섹션 갱신.

yfinance 무료 스크리너(undervalued_large_caps + undervalued_growth_stocks)로 후보를 받아
PER+PBR 합산 랭킹 상위 QUOTA(현재 10)종을 auto:screened 섹션에 기록한다(히스테리시스:
기존 편입 종목은 상위 QUOTA×2위 이내면 유지 — 데이터 연속성 보호). 허브 수요 조회
(/automation/stock-demand)로 최근 14일 질문 상위 미수집 종목을 auto:demand 섹션(상한 5)에
기록한다. 코어 섹션은 절대 건드리지 않으며, 파일 갱신은 temp→rename 원자적으로 한다.

실행:
    python scripts/screen_us_undervalued.py            # 워치리스트 갱신
    python scripts/screen_us_undervalued.py --dry-run  # 판단만 출력 (파일 불변)

백엔드 PC cron 예시(주 1회, 토 06:30 — 주간 펀더멘털 수집 전):
    30 6 * * 6 flock -n /tmp/screen_us.lock -c 'cd /path/to/minseok && ../venv/bin/python scripts/screen_us_undervalued.py' >> ~/screen_us.log 2>&1
"""

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))

from core.key.secret_manager import get_secret_manager  # noqa: E402

_secrets = get_secret_manager()

HUB_URL = _secrets.get("HUB_URL", "http://localhost:8000")
TOKEN = _secrets.get("N8N_INBOUND_TOKEN")
WATCHLIST = ROOT / "scripts" / "news_watchlist.txt"

SCREEN_QUERIES = ("undervalued_large_caps", "undervalued_growth_stocks")
QUOTA = 10                         # auto:screened 정원
KEEP_RANK = QUOTA * 2              # 히스테리시스 — 기존 편입 종목은 이 순위 안이면 유지
MIN_MARKET_CAP = 5_000_000_000     # $5B — 대형주만
DEMAND_QUOTA = 5                   # auto:demand 정원
DEMAND_DAYS = 14                   # 이 기간 질문 없으면 자연 퇴출

SCREENED_BEGIN = "# === auto:screened"
SCREENED_END = "# === /auto:screened ==="
DEMAND_BEGIN = "# === auto:demand"
DEMAND_END = "# === /auto:demand ==="


def parse_sections(text: str) -> tuple[list[str], dict[str, list[str]]]:
    """파일 전체 줄과 {섹션: 내용 줄들}. 마커 줄 자체는 내용에서 제외."""
    lines = text.splitlines()
    sections: dict[str, list[str]] = {"screened": [], "demand": []}
    current: str | None = None
    for line in lines:
        if line.startswith(SCREENED_BEGIN) and not line.startswith(SCREENED_END):
            current = "screened"
        elif line.startswith(DEMAND_BEGIN) and not line.startswith(DEMAND_END):
            current = "demand"
        elif line.startswith(SCREENED_END) or line.startswith(DEMAND_END):
            current = None
        elif current is not None and line.strip():
            sections[current].append(line.strip())
    return lines, sections


def entry_ticker(line: str) -> str:
    """워치리스트 줄(한글명|티커|쿼리)에서 티커."""
    parts = [p.strip() for p in line.split("|")]
    return parts[1] if len(parts) > 1 else ""


def all_tickers(lines: list[str]) -> set[str]:
    return {
        entry_ticker(line.strip())
        for line in lines
        if line.strip() and not line.strip().startswith("#") and "|" in line
    }


def fetch_candidates() -> list[dict]:
    """스크리너 2종 합집합 — 실패는 상위에서 처리(파일 무변경)."""
    merged: dict[str, dict] = {}
    for query in SCREEN_QUERIES:
        response = yf.screen(query, count=100)
        for quote in (response or {}).get("quotes", []):
            symbol = quote.get("symbol", "")
            if symbol:
                merged.setdefault(symbol, quote)
    return list(merged.values())


def rank_candidates(quotes: list[dict], exclude: set[str]) -> list[dict]:
    """필터 후 PER+PBR 합산 순위(작을수록 저평가) 오름차순."""
    eligible = [
        q for q in quotes
        if q.get("symbol") not in exclude
        and "." not in q.get("symbol", "")          # 미국 상장만 (해외 접미 제외)
        and "-" not in q.get("symbol", "")          # 우선주·클래스 중복(PBR-A 등) 제외
        and (q.get("marketCap") or 0) >= MIN_MARKET_CAP
        and (q.get("trailingPE") or 0) > 0
    ]
    by_pe = sorted(eligible, key=lambda q: q["trailingPE"])
    pe_rank = {q["symbol"]: i for i, q in enumerate(by_pe)}
    with_pbr = sorted(
        (q for q in eligible if (q.get("priceToBook") or 0) > 0),
        key=lambda q: q["priceToBook"],
    )
    pbr_rank = {q["symbol"]: i for i, q in enumerate(with_pbr)}
    # PBR 결측이면 PER 순위만 두 배로 (동일 축 반복 — 결측 페널티 없음)
    scored = sorted(
        eligible,
        key=lambda q: pe_rank[q["symbol"]] + pbr_rank.get(q["symbol"], pe_rank[q["symbol"]]),
    )
    return scored


def drop_ineligible(ranked: list[dict]) -> list[dict]:
    """상위 후보 중 정책 부적격 제외 — 상위 KEEP_RANK*2 종목만 yf .info로 확인(주 1회 소량 호출).

    - 한국 기업 ADR(KEP 등): '한국은 코어 2종 외 추가 금지' 정책
    - sector 없는 종목: 폐쇄형 펀드·트러스트(CEF 등) — PER/PBR이 사업 밸류에이션이 아니다
    조회 실패는 통과(best-effort)."""
    out: list[dict] = []
    for i, q in enumerate(ranked):
        if i < KEEP_RANK * 2:
            try:
                info = yf.Ticker(q["symbol"]).info
                if info.get("country") == "South Korea":
                    print(f"  제외(한국 기업 ADR): {q['symbol']}")
                    continue
                if not info.get("sector"):
                    print(f"  제외(펀드·트러스트 — sector 없음): {q['symbol']}")
                    continue
            except Exception:
                pass
        out.append(q)
    return out


def apply_hysteresis(current: list[str], ranked: list[dict]) -> list[dict]:
    """기존 편입 종목은 상위 KEEP_RANK 이내면 유지, 빈자리만 신규 상위로 채운다."""
    current = list(dict.fromkeys(current))  # 파일 수동 오염(중복 줄) 방어
    rank_pos = {q["symbol"]: i for i, q in enumerate(ranked)}
    by_symbol = {q["symbol"]: q for q in ranked}
    kept = [by_symbol[t] for t in current if t in rank_pos and rank_pos[t] < KEEP_RANK]
    for q in ranked:
        if len(kept) >= QUOTA:
            break
        if q not in kept:
            kept.append(q)
    return kept[:QUOTA]


def screened_line(quote: dict) -> str:
    symbol = quote["symbol"]
    name = (quote.get("longName") or quote.get("shortName") or symbol).strip()
    name = name.replace("|", " ")  # 파이프는 워치리스트 구분자 — 기업명에 섞이면 파싱 붕괴
    return f"{name}|{symbol}|{name} stock"


def _base(ticker: str) -> str:
    """거래소 접미(.KS/.KQ)를 벗긴 표준형 — 백엔드 수요 집계와 같은 규칙."""
    t = ticker.strip().upper()
    for suffix in (".KS", ".KQ"):
        if t.endswith(suffix):
            return t[: -len(suffix)]
    return t


def fetch_demand(exclude: set[str]) -> list[str] | None:
    """허브 수요 상위 → 유효 티커만. 조회 실패면 None(기존 섹션 유지)."""
    try:
        res = requests.get(
            f"{HUB_URL}/automation/stock-demand",
            params={"days": DEMAND_DAYS, "limit": DEMAND_QUOTA * 3},
            headers={"X-Webhook-Token": TOKEN},
            timeout=15,
        )
        res.raise_for_status()
        rows = res.json()
        if not isinstance(rows, list):
            raise ValueError(f"예상 밖 응답 형태: {type(rows).__name__}")
    except Exception as e:
        print(f"수요 조회 실패(auto:demand 유지) — {e}")
        return None

    # 이미 수집 중인 종목인지 판정할 때 거래소 접미를 벗겨 맞춘다 — 수요는 표준형(005930)으로
    # 쌓이고 워치리스트는 저장 티커(005930.KS)라 문자열 그대로는 영영 안 겹친다.
    exclude_base = {_base(t) for t in exclude}
    lines: list[str] = []
    for row in rows:
        ticker = str(row.get("ticker", "")).strip().upper()
        if not ticker or ticker in exclude or _base(ticker) in exclude_base:
            continue
        try:  # 쓰레기 질의(오타 티커) 편입 방지 — 시세 존재 확인 1회
            if yf.Ticker(ticker).history(period="5d").empty:
                continue
        except Exception:
            continue
        lines.append(f"{ticker}|{ticker}")
        if len(lines) >= DEMAND_QUOTA:
            break
    return lines


def rewrite(lines: list[str], screened: list[str], demand: list[str] | None) -> str:
    """auto 섹션 내용만 교체한 새 파일 텍스트."""
    out: list[str] = []
    current: str | None = None
    for line in lines:
        if line.startswith(SCREENED_BEGIN) and not line.startswith(SCREENED_END):
            out.append(line)
            out.extend(screened)
            current = "screened"
        elif line.startswith(DEMAND_BEGIN) and not line.startswith(DEMAND_END):
            out.append(line)
            if demand is not None:
                out.extend(demand)
                current = "demand"
            else:
                current = "keep-demand"  # 조회 실패 — 기존 내용 통과
        elif line.startswith(SCREENED_END) or line.startswith(DEMAND_END):
            out.append(line)
            current = None
        elif current in ("screened", "demand"):
            continue  # 기존 섹션 내용은 버린다(새 내용으로 대체됨)
        else:
            out.append(line)
    return "\n".join(out) + "\n"


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 스크리닝 시작", flush=True)

    text = WATCHLIST.read_text(encoding="utf-8")
    lines, sections = parse_sections(text)
    current_screened = [entry_ticker(line) for line in sections["screened"]]
    current_demand = [entry_ticker(line) for line in sections["demand"]]
    core_tickers = all_tickers(lines) - set(current_screened) - set(current_demand)

    try:
        candidates = fetch_candidates()
    except Exception as e:
        print(f"스크리너 조회 실패 — 파일 무변경 종료: {e}")
        sys.exit(1)  # cron이 실패를 감지할 수 있게 비정상 종료코드

    ranked = drop_ineligible(rank_candidates(candidates, exclude=core_tickers))
    chosen = apply_hysteresis(current_screened, ranked)
    screened_lines = [screened_line(q) for q in chosen]

    print(f"후보 {len(candidates)} → 필터 통과 {len(ranked)}")
    for i, q in enumerate(ranked[:KEEP_RANK]):
        mark = "★유지" if q["symbol"] in current_screened and q in chosen else (
            "＋신규" if q in chosen else "")
        print(f"  {i + 1:2d}. {q['symbol']:6s} PER {q.get('trailingPE', 0):7.1f} "
              f"PBR {q.get('priceToBook') or 0:6.2f} {mark}")
    dropped = [t for t in current_screened if t not in {q['symbol'] for q in chosen}]
    if dropped:
        print(f"  퇴출: {', '.join(dropped)}")

    exclude_for_demand = core_tickers | {q["symbol"] for q in chosen}
    demand_lines = fetch_demand(exclude_for_demand)
    if demand_lines is not None:
        print(f"수요 편입: {[entry_ticker(line) for line in demand_lines] or '없음'}")

    if dry_run:
        print("(dry-run — 파일 불변)")
        return

    new_text = rewrite(lines, screened_lines, demand_lines)
    fd, tmp_path = tempfile.mkstemp(dir=WATCHLIST.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(new_text)
        os.replace(tmp_path, WATCHLIST)  # 원자적 교체 — 수집기가 중간 상태를 읽지 않게
    except BaseException:
        try:
            os.unlink(tmp_path)  # 실패 시 temp 잔재 정리 (원본은 os.replace 원자성으로 무결)
        except OSError:
            pass
        raise
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 워치리스트 갱신 완료 "
          f"(screened {len(screened_lines)} · demand {'유지' if demand_lines is None else len(demand_lines)})")


if __name__ == "__main__":
    main()
