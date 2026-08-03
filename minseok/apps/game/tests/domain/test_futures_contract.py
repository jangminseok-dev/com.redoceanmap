"""지수 선물 — 계약 시리즈·베이시스·만기 수렴.

여기서 고정하는 계약 중 하나는 **"청산 엔진이 필요 없다"는 가정**이다. 만기 구간의 지수
변동이 증거금을 넘기 시작하면 손실 상한만으로는 부족해지므로, 이 테스트가 회귀 알람이다.
"""
import math
import statistics

import pytest

from game.domain.clock.game_epoch import SEASON_TICKS
from game.domain.market import futures_contract as fut
from game.domain.market import price_engine
from game.domain.market.symbol_params import SYMBOLS


# --- 지수 -------------------------------------------------------------------

def test_지수는_시작_시점에_기준값이다():
    assert price_engine.index_at(0) == price_engine.INDEX_BASE_POINT


def test_지수는_기하평균이라_로그공간에서_평균이다():
    """산술평균이면 로그정규 볼록성 때문에 구조적 상승 편향이 생긴다 —
    μ를 0으로 중심화해도 지수만 오르고, 그러면 선물 롱이 언제나 유리해진다."""
    tick = 12_345
    expected = price_engine.INDEX_BASE_POINT * math.exp(
        sum(math.log(price_engine.price_at(s, tick) / s.base_price_krw) for s in SYMBOLS)
        / len(SYMBOLS)
    )
    assert price_engine.index_at(tick) == max(1, round(expected))


def test_지수는_결정론이다():
    assert len({price_engine.index_at(9_999) for _ in range(20)}) == 1


# --- 계약 시리즈 -------------------------------------------------------------

def test_근월물은_만기_주기마다_넘어간다():
    first = fut.front_contract(0)
    assert first.expiry_tick == fut.FUTURES_EXPIRY_TICKS
    # 만기 직전까지는 같은 계약, 만기를 지나면 다음 계약
    assert fut.front_contract(fut.FUTURES_EXPIRY_TICKS - 1).code == first.code
    assert fut.front_contract(fut.FUTURES_EXPIRY_TICKS).code != first.code


def test_계약_만기는_시즌을_넘지_않는다():
    assert fut.front_contract(SEASON_TICKS - 1).expiry_tick <= SEASON_TICKS


# --- 베이시스 ---------------------------------------------------------------

def test_만기에는_선물가가_현물_정산가와_같다():
    """만기 수렴이 규칙이 아니라 수식의 성질이어야 한다(τ=0이면 지수항이 1)."""
    for step in (1, 5, 40):
        expiry = step * fut.FUTURES_EXPIRY_TICKS
        assert fut.futures_price(expiry, expiry) == fut.settlement_price(expiry)
        assert fut.basis_ratio(expiry, expiry) == 0.0


def test_잔존이_줄수록_베이시스가_줄어든다():
    expiry = 20 * fut.FUTURES_EXPIRY_TICKS
    far = abs(fut.basis_ratio(expiry, expiry - fut.FUTURES_EXPIRY_TICKS))
    near = abs(fut.basis_ratio(expiry, expiry - 10))
    assert near < far


def test_계약마다_콘탱고와_백워데이션이_갈린다():
    """전량 콘탱고면 숏이 방향성 없이 공짜 수익을 얻는다."""
    ratios = [
        fut.basis_ratio(step * fut.FUTURES_EXPIRY_TICKS, (step - 1) * fut.FUTURES_EXPIRY_TICKS)
        for step in range(1, 60)
    ]
    assert any(r > 0 for r in ratios), "콘탱고 계약이 하나도 없다"
    assert any(r < 0 for r in ratios), "백워데이션 계약이 하나도 없다"


def test_베이시스는_결정론이다():
    expiry = 10 * fut.FUTURES_EXPIRY_TICKS
    assert len({fut.futures_price(expiry, expiry - 50) for _ in range(20)}) == 1


# --- 청산 엔진 불필요 가정 (회귀 알람) ----------------------------------------

def test_만기_구간_지수_변동이_증거금에_못_미친다():
    """**이 가정이 깨지면 선물에도 청산 엔진이 필요해진다.**

    깨졌을 때의 선택지는 ① 증거금률을 올리거나 ② 만기를 줄이거나 ③ 틱 스캔 청산을 도입
    (지수 평가가 0.58ms라 96ms/포지션 — 지갑 응답 목표를 넘긴다)이다.
    """
    moves = []
    for start in range(0, SEASON_TICKS - fut.FUTURES_EXPIRY_TICKS, fut.FUTURES_EXPIRY_TICKS):
        before = price_engine.index_at(start)
        after = price_engine.index_at(start + fut.FUTURES_EXPIRY_TICKS)
        moves.append(abs((after - before) / before))

    assert max(moves) < fut.FUTURES_MARGIN_RATIO, (
        f"만기 구간 최대 변동 {max(moves):.1%}가 증거금 {fut.FUTURES_MARGIN_RATIO:.0%}를 넘었다"
    )
    # 여유가 얼마나 남았는지도 함께 고정한다 — 경계에 붙으면 미리 알아야 한다
    assert statistics.pstdev(moves) < fut.FUTURES_MARGIN_RATIO / 3


def test_계약_명목과_증거금이_초기자본에_맞는다():
    """1계약이 초기자본을 통째로 먹으면 게임이 되지 않는다."""
    value = fut.contract_value_krw(price_engine.INDEX_BASE_POINT)
    margin = value * fut.FUTURES_MARGIN_RATIO
    assert 300_000 <= value <= 800_000
    assert margin <= 200_000  # 초기자본 100만원에서 여러 계약을 잡을 수 있다


@pytest.mark.parametrize("point", [1, 1_000, 5_000])
def test_계약_금액은_포인트에_비례한다(point):
    assert fut.contract_value_krw(point) == point * fut.CONTRACT_MULTIPLIER_KRW
