"""가격 엔진 재현성·성질 검증 (game-harness §8-1 · §8-2).

이 파일이 없으면 §1의 결정론 규칙은 문서상의 주장일 뿐이다.
"""
from __future__ import annotations

import math
import statistics
import subprocess
import sys
from pathlib import Path

import game
from game.domain.clock.game_epoch import SEASON_TICKS, TICKS_PER_GAME_DAY
from game.domain.market import price_engine
from game.domain.market.symbol_params import SIGMA_GAME_MULTIPLIER, SYMBOLS

_SAMPLE = SYMBOLS[0]
_APPS_DIR = str(Path(game.__file__).resolve().parent.parent)


# --- 재현성 3종 (harness §8-1) ----------------------------------------------

def test_재현성1_같은_틱을_100번_물어도_같은_값이다():
    values = {price_engine.price_at(_SAMPLE, 1234) for _ in range(100)}
    assert len(values) == 1


def test_재현성2_호출_순서가_결과를_바꾸지_않는다():
    ascending = [price_engine.price_at(_SAMPLE, t) for t in range(500, 520)]
    descending = [price_engine.price_at(_SAMPLE, t) for t in range(519, 499, -1)][::-1]
    assert ascending == descending

    scattered = {t: price_engine.price_at(_SAMPLE, t) for t in (510, 501, 519, 505, 500)}
    assert all(scattered[t] == ascending[t - 500] for t in scattered)


def test_재현성3_다른_프로세스에서_계산해도_같은_값이다():
    """내장 hash() 혼입을 잡는다 — PYTHONHASHSEED가 다르면 값이 갈린다."""
    expected = price_engine.price_at(_SAMPLE, 7777)
    script = (
        "from game.domain.market import price_engine;"
        "from game.domain.market.symbol_params import SYMBOLS;"
        "print(price_engine.price_at(SYMBOLS[0], 7777))"
    )
    for seed in ("0", "12345"):
        out = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env={"PYTHONHASHSEED": seed, "PYTHONPATH": _APPS_DIR},
            check=True,
        )
        assert int(out.stdout.strip()) == expected


# --- 성질 -------------------------------------------------------------------

def test_시작_틱_가격은_기준가와_같다():
    for params in SYMBOLS:
        assert price_engine.price_at(params, 0) == params.base_price_krw


def test_가격은_항상_양의_정수다():
    for params in SYMBOLS:
        for tick in (0, 1, 5_000, 43_200):
            price = price_engine.price_at(params, tick)
            assert isinstance(price, int) and price > 0


def test_시즌_종료_후에는_가격이_멈춘다():
    last = price_engine.price_at(_SAMPLE, SEASON_TICKS)
    assert price_engine.price_at(_SAMPLE, SEASON_TICKS + 10_000) == last


def test_일간_변동성이_목표치_부근이다():
    """브리지 스케일링이 어긋나면 여기서 잡힌다(목표 = sigma_daily × 배수)."""
    for params in SYMBOLS[:4]:
        returns = [
            (price_engine.price_at(params, d * TICKS_PER_GAME_DAY)
             - price_engine.price_at(params, (d - 1) * TICKS_PER_GAME_DAY))
            / price_engine.price_at(params, (d - 1) * TICKS_PER_GAME_DAY)
            for d in range(1, 400)
        ]
        target = params.sigma_daily * SIGMA_GAME_MULTIPLIER
        assert math.isclose(statistics.pstdev(returns), target, rel_tol=0.30)


# --- 분포 회귀 (harness §8-2) -----------------------------------------------

def test_분포회귀_종목별_수익률이_한_값에_몰리지_않는다():
    """예측 스냅샷 전량 NEUTRAL 같은 '조용히 잘못된 값'을 잡는다."""
    finals = [price_engine.price_at(p, 5_400) / p.base_price_krw for p in SYMBOLS]
    assert statistics.pstdev(finals) > 0.01
    assert len(set(finals)) == len(SYMBOLS)


def test_분포회귀_인접_틱이_계단처럼_반복되지_않는다():
    """차트가 계단으로 보이면 브리지가 일 경계에서만 움직인다는 뜻이다.

    2단계 완료 판정의 "차트가 계단·직선이 아니다"를 육안 대신 수치로 본다.
    """
    for params in SYMBOLS:
        prices = [price_engine.price_at(params, t) for t in range(1_000, 1_120)]
        assert len(set(prices)) / len(prices) > 0.5, f"{params.symbol} 계단형"


def test_분포회귀_가격이_한_방향_직선이_아니다():
    """상승·하락이 섞여야 시세로 읽힌다. 한쪽으로만 가면 브리지가 죽고 드리프트만 남은 것이다."""
    for params in SYMBOLS:
        prices = [price_engine.price_at(params, t) for t in range(2_000, 2_240)]
        diffs = [b - a for a, b in zip(prices, prices[1:])]
        up_ratio = sum(1 for d in diffs if d > 0) / len(diffs)
        assert 0.2 < up_ratio < 0.8, f"{params.symbol} 단조 추세 (상승비율 {up_ratio:.2f})"


def test_시리즈는_오름차순_틱이고_요청_개수만큼_나온다():
    series = price_engine.price_series(_SAMPLE, end_tick=1_000, count=60)
    assert len(series) == 60
    assert [t for t, _ in series] == list(range(941, 1_001))


def test_시리즈는_에포크_이전으로_내려가지_않는다():
    series = price_engine.price_series(_SAMPLE, end_tick=10, count=60)
    assert series[0][0] == 0
    assert len(series) == 11


# --- 일봉 -------------------------------------------------------------------

def test_봉의_고저는_시종가를_감싼다():
    """OHLC 불변식 — 깨지면 봉 몸통이 심지 밖으로 나간다."""
    for params in SYMBOLS[:4]:
        for candle in price_engine.daily_candles(params, end_tick=12_345, days=7):
            assert candle.low_krw <= min(candle.open_krw, candle.close_krw)
            assert max(candle.open_krw, candle.close_krw) <= candle.high_krw


def test_완결된_봉의_종가는_그날_마지막_틱_가격이다():
    """봉과 라인 차트가 같은 값을 그려야 한다 — 갈라지면 어느 쪽이 정본인지 알 수 없다."""
    candles = price_engine.daily_candles(_SAMPLE, end_tick=12_345, days=7)
    for candle in candles[:-1]:  # 마지막 봉은 진행 중이라 제외
        last_tick = candle.game_day * TICKS_PER_GAME_DAY + TICKS_PER_GAME_DAY - 1
        assert candle.close_krw == price_engine.price_at(_SAMPLE, last_tick)
        assert candle.open_krw == price_engine.price_at(
            _SAMPLE, candle.game_day * TICKS_PER_GAME_DAY
        )


def test_진행중인_봉은_현재_틱에서_멈춘다():
    """미래 틱을 만들지 않는다(§1-6) — 오늘 봉의 종가는 지금 가격이다."""
    now = 12_345
    candles = price_engine.daily_candles(_SAMPLE, end_tick=now, days=3)
    assert candles[-1].close_krw == price_engine.price_at(_SAMPLE, now)
    assert candles[-1].game_day == now // TICKS_PER_GAME_DAY


def test_봉은_에포크_이전으로_내려가지_않는다():
    candles = price_engine.daily_candles(_SAMPLE, end_tick=90, days=7)
    assert candles[0].game_day == 0
    assert len(candles) == 2  # 0일차 + 1일차(진행 중)
