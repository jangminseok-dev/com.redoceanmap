"""가상 재무 검증 — 11단계에서 보류했던 PER·ROE의 근거(§13-3 어닝 캘린더)."""
import pytest

from game.domain.clock.game_epoch import QUARTERS_PER_SEASON
from game.domain.market import fundamentals as f
from game.domain.market.symbol_params import SYMBOLS

PLAIN = SYMBOLS[0]
MEME = next(s for s in SYMBOLS if s.meme)


# --- 결정론 ------------------------------------------------------------------

def test_같은_분기는_항상_같은_재무다():
    """저장하지 않는 값이라 언제 물어도 같아야 한다(harness §1-A)."""
    assert len({f.at_quarter(PLAIN, 3) for _ in range(20)}) == 1


def test_분기가_바뀌면_실적이_갱신된다():
    """어닝 시즌 — 이게 없으면 PER이 가격 변동만 따라가는 죽은 값이 된다."""
    eps = [f.at_quarter(PLAIN, q).assumed_eps_krw for q in range(1, QUARTERS_PER_SEASON + 1)]
    assert len(set(eps)) > 1


def test_분기_범위를_벗어나면_양끝으로_고정된다():
    assert f.at_quarter(PLAIN, 0).game_quarter == 1
    assert f.at_quarter(PLAIN, 99).game_quarter == QUARTERS_PER_SEASON


# --- 밸류에이션 ---------------------------------------------------------------

def test_가격이_오르면_PER도_오른다():
    """실적을 가격에서 역산하면 PER이 상수가 된다 — 그러면 아무 정보가 없다."""
    fin = f.at_quarter(PLAIN, 2)
    cheap = f.value_at(PLAIN, 50_000, fin)
    rich = f.value_at(PLAIN, 150_000, fin)
    assert rich.per > cheap.per
    assert rich.pbr > cheap.pbr
    assert rich.market_cap_krw > cheap.market_cap_krw


def test_적자면_PER을_만들지_않는다():
    """음수 PER은 화면에서 '싸다'로 오독된다 — 실제 증권 앱도 칸을 비운다."""
    fin = f.at_quarter(MEME, 2)
    assert fin.assumed_eps_krw < 0
    assert f.value_at(MEME, 10_000, fin).per is None


def test_밈_종목은_적자다():
    """GME·AMC가 그랬듯 적자 상태 자체가 그 종목의 성격이다."""
    for params in (s for s in SYMBOLS if s.meme):
        for q in (1, 4, 8):
            assert f.at_quarter(params, q).assumed_eps_krw < 0


def test_시가총액은_주가와_주식수의_곱이다():
    fin = f.at_quarter(PLAIN, 1)
    v = f.value_at(PLAIN, 77_777, fin)
    assert v.market_cap_krw == 77_777 * fin.assumed_shares_outstanding


# --- 업종 특성 ----------------------------------------------------------------

def test_업종마다_기준_PER이_다르다():
    """금융이 소프트웨어와 같은 PER을 받으면 업종 개념이 무의미해진다."""
    def per_of(group: str) -> float:
        params = next(s for s in SYMBOLS if s.sector_group == group)
        fin = f.at_quarter(params, 1)
        return f.value_at(params, params.base_price_krw, fin).per

    assert per_of("소프트웨어·플랫폼") > per_of("금융·핀테크") * 2


def test_흑자_종목은_자본이_쌓여_간다():
    """이익잉여금 누적 — 흑자면 BPS가 늘고 적자면 깎인다."""
    early = f.at_quarter(PLAIN, 1).assumed_bps_krw
    late = f.at_quarter(PLAIN, QUARTERS_PER_SEASON).assumed_bps_krw
    assert late > early


def test_서프라이즈는_직전_분기_대비다():
    for q in range(1, QUARTERS_PER_SEASON + 1):
        assert f.at_quarter(PLAIN, q).surprise in ("beat", "miss", "inline")
    assert f.at_quarter(PLAIN, 1).surprise == "inline"  # 비교 대상이 없다


def test_ROE는_EPS와_BPS의_비율이다():
    for q in (1, 5, 8):
        fin = f.at_quarter(PLAIN, q)
        assert fin.assumed_roe == pytest.approx(
            fin.assumed_eps_krw / fin.assumed_bps_krw, abs=1e-3
        )


def test_전_종목이_계산되고_값이_유한하다():
    for params in SYMBOLS:
        fin = f.at_quarter(params, 4)
        assert fin.assumed_shares_outstanding > 0
        assert fin.assumed_bps_krw > 0
        v = f.value_at(params, params.base_price_krw, fin)
        assert v.market_cap_krw > 0
        assert v.pbr is None or v.pbr > 0


# --- 배당 --------------------------------------------------------------------

def test_적자_종목은_배당이_없다():
    """실제 기업이 그렇다. 밈 종목이 배당까지 주면 적자라는 성격이 무의미해진다."""
    for params in (s for s in SYMBOLS if s.meme):
        for q in range(1, QUARTERS_PER_SEASON + 1):
            assert f.dividend_per_share(params, q) == 0


def test_배당성향이_업종마다_다르다():
    """성장주는 재투자하고 통신·금융은 많이 준다 — 실제 시장의 특성이다."""
    def yield_of(group: str) -> float:
        params = next(s for s in SYMBOLS if s.sector_group == group)
        return f.dividend_per_share(params, 3) / params.base_price_krw

    assert yield_of("통신·미디어") > yield_of("소프트웨어·플랫폼") * 2


def test_배당락이_반드시_따라온다():
    """배당만 주고 배당락이 없으면 분기 경계만 넘기는 것이 공짜 수익이 된다."""
    params = next(s for s in SYMBOLS if not s.meme and f.dividend_per_share(s, 2) > 0)
    events = f.quarterly_events(params)
    drops = [e for e in events if "배당락" in e.headline]
    assert drops, f"{params.name}은 배당을 주는데 배당락 이벤트가 없다"
    assert all(e.shock < 0 for e in drops)


def test_보유_구간의_배당만_센다():
    params = next(s for s in SYMBOLS if not s.meme and f.dividend_per_share(s, 2) > 0)
    boundary = 90 * 60  # 2분기 시작
    assert f.dividends_between(params, boundary - 10, boundary - 1) == 0  # 경계 전에 청산
    assert f.dividends_between(params, boundary - 10, boundary + 10) > 0  # 경계를 넘김


# --- 유상증자 ------------------------------------------------------------------

def test_유상증자는_주식수를_늘리고_EPS를_희석한다():
    """희석이 없으면 유상증자가 이름뿐인 이벤트가 된다."""
    target = next(
        (s for s in SYMBOLS for q in range(2, 9) if f.rights_issue_ratio(s, q) > 0), None
    )
    assert target is not None, "시즌 전체에 유상증자가 한 번도 없다"
    quarter = next(q for q in range(2, 9) if f.rights_issue_ratio(target, q) > 0)
    assert f.shares_outstanding(target, quarter) > f.shares_outstanding(target, quarter - 1)


def test_주식수는_한번_늘면_줄지_않는다():
    for params in SYMBOLS[:6]:
        counts = [f.shares_outstanding(params, q) for q in range(1, QUARTERS_PER_SEASON + 1)]
        assert all(b >= a for a, b in zip(counts, counts[1:]))


def test_밈_종목이_유상증자를_더_자주_한다():
    """AMC·GME가 주가가 뛸 때마다 증자로 자금을 조달했다."""
    def count(meme: bool) -> int:
        pool = [s for s in SYMBOLS if s.meme == meme]
        return sum(1 for s in pool for q in range(2, 9) if f.rights_issue_ratio(s, q) > 0) / len(pool)

    assert count(True) > count(False)
