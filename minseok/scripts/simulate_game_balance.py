"""게임 밸런스 실측 — 무작위 전략의 분기 손익 분포 (game-strategy §3-4 · §4-6).

**계수 조정은 이 리포트를 근거로만 한다.** 감으로 고치지 않는다.

`random`을 쓰지 않는다. 전략 선택도 blake2b 시드로 뽑아 **리포트가 재현 가능**하게 한다 —
계수를 바꾸고 다시 돌렸을 때 차이가 계수 때문인지 표본 때문인지 가릴 수 있어야 한다.

실행:
    cd minseok && PYTHONPATH=apps python3 scripts/simulate_game_balance.py
    cd minseok && PYTHONPATH=apps python3 scripts/simulate_game_balance.py --runs 2000
"""
from __future__ import annotations

import argparse
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps"))

from game.domain.clock.game_epoch import GAME_DAYS_PER_QUARTER, TICKS_PER_GAME_DAY  # noqa: E402
from game.domain.commerce import store_simulation as store_sim  # noqa: E402
from game.domain.market import price_engine  # noqa: E402
from game.domain.market.symbol_params import SYMBOLS  # noqa: E402
from game.domain.rng.deterministic import uniform  # noqa: E402
from game.domain.trading.trading_rules import (  # noqa: E402
    INITIAL_CASH_KRW,
    Side,
    close_result,
    entry_cost,
    investable_cash,
    max_quantity,
)

QUARTER_TICKS = GAME_DAYS_PER_QUARTER * TICKS_PER_GAME_DAY
TRADES_PER_QUARTER = 12  # 무작위 플레이어가 분기 동안 여는 포지션 수


@dataclass(frozen=True)
class Quantiles:
    p10: float
    p50: float
    p90: float
    loss_ratio: float
    mean: float


def _quantiles(values: list[float]) -> Quantiles:
    ordered = sorted(values)
    n = len(ordered)
    pick = lambda q: ordered[min(n - 1, int(n * q))]  # noqa: E731
    return Quantiles(
        p10=pick(0.10),
        p50=pick(0.50),
        p90=pick(0.90),
        loss_ratio=sum(1 for v in ordered if v < 0) / n,
        mean=statistics.fmean(ordered),
    )


def simulate_investor(run: int) -> float:
    """무작위 매매 한 판의 분기 수익률(%).

    종목·방향·보유 기간을 시드로 뽑는다. 전략이랄 것이 없는 플레이어의 기대값이
    밸런스의 기준선이다.
    """
    cash = INITIAL_CASH_KRW
    for trade in range(TRADES_PER_QUARTER):
        key = f"{run}|{trade}"
        symbol = SYMBOLS[int(uniform("bal-symbol", key) * len(SYMBOLS)) % len(SYMBOLS)]
        side = Side.LONG if uniform("bal-side", key) < 0.6 else Side.SHORT
        # 분기를 균등 분할해 진입하고, 다음 진입 전에 청산한다
        span = QUARTER_TICKS // TRADES_PER_QUARTER
        entry_tick = trade * span
        hold = 1 + int(uniform("bal-hold", key) * (span - 1))
        exit_tick = entry_tick + hold

        entry_price = price_engine.price_at(symbol, entry_tick)
        # 가진 돈의 20~80%를 넣는다
        budget = int(investable_cash(cash) * (0.2 + 0.6 * uniform("bal-size", key)))
        quantity = max_quantity(budget + (cash - investable_cash(cash)), entry_price)
        if quantity <= 0:
            continue

        cost = entry_cost(entry_price, quantity)
        if cost.total_krw > investable_cash(cash):
            continue
        cash -= cost.total_krw

        result = close_result(
            side=side,
            entry_price_krw=entry_price,
            exit_price_krw=price_engine.price_at(symbol, exit_tick),
            quantity=quantity,
            holding_game_days=hold / TICKS_PER_GAME_DAY,
            entry_fee_krw=cost.fee_krw,
        )
        cash += result.proceeds_krw

    return (cash - INITIAL_CASH_KRW) / INITIAL_CASH_KRW * 100


# 창업 밸런스는 적합도가 지배한다. 무작위로 상권·업종을 고르면 적합도가 어떻게 분포하는지가
# 곧 "절반은 적자"의 성립 여부다. 실데이터 없이 돌 수 있게 적합도를 균등 샘플링한다.
FITNESS_MIN, FITNESS_MAX = 0.4, 1.6
SALES_PER_STORE = 30_000_000
TICKET_PRICE = 5_000
WEEKDAY_SHARE = (0.15, 0.14, 0.14, 0.15, 0.16, 0.14, 0.12)


def simulate_founder(run: int, budget_krw: int, facility_score: int) -> float:
    """무작위 입지에 창업한 한 판의 분기 수익률(투입 자본 대비 %)."""
    fitness = FITNESS_MIN + (FITNESS_MAX - FITNESS_MIN) * uniform("bal-fitness", str(run))
    location = 0.6 + uniform("bal-location", str(run))
    scale = store_sim.scale_for_budget(SALES_PER_STORE, location, facility_score, budget_krw)
    setup = store_sim.StoreSetup(
        store_id=run,
        service_code="CS100010",
        opened_game_day=0,
        store_scale=scale,
        observed_sales_per_store=SALES_PER_STORE,
        observed_ticket_price=TICKET_PRICE,
        fitness=fitness,
        rent_location_factor=location,
        area_weekday_share=WEEKDAY_SHARE,
    )
    decision = store_sim.StoreDecision(
        price_factor=1.0, staff_count=2, facility_score=facility_score
    )
    profit = sum(
        store_sim.simulate_day(setup, decision, day).profit_krw
        for day in range(GAME_DAYS_PER_QUARTER)
    )
    return profit / budget_krw * 100


def _print(title: str, q: Quantiles, target: str) -> None:
    print(f"\n{title}")
    print(f"  하위 10%  {q.p10:+9.1f}%")
    print(f"  중앙값    {q.p50:+9.1f}%   ← 밸런스 계약의 기준")
    print(f"  상위 10%  {q.p90:+9.1f}%")
    print(f"  평균      {q.mean:+9.1f}%")
    print(f"  손실 비율 {q.loss_ratio:9.1%}")
    print(f"  목표: {target}")


def main() -> None:
    parser = argparse.ArgumentParser(description="게임 밸런스 실측")
    parser.add_argument("--runs", type=int, default=1000)
    parser.add_argument("--budget", type=int, default=3_000_000, help="창업 투입 자본")
    parser.add_argument("--facility", type=int, default=300, help="창업 시설 점수")
    args = parser.parse_args()

    print(f"게임 1분기(90게임일 · 현실 3.75일) · 표본 {args.runs:,}회")
    print("=" * 62)

    investor = [simulate_investor(run) for run in range(args.runs)]
    _print("■ 모의투자 — 무작위 매매", _quantiles(investor), "중앙값 +5~15% · 손실 35~45%")

    founder = [
        simulate_founder(run, args.budget, args.facility) for run in range(args.runs)
    ]
    _print(
        f"■ 상권 창업 — 무작위 입지 (자본 {args.budget:,}원 · 시설 {args.facility}점)",
        _quantiles(founder),
        "중앙값 소폭 적자 · 손실 절반 내외",
    )

    print("\n" + "=" * 62)
    print("이 표를 근거로만 계수를 조정한다(game-strategy §3-4). 시드가 고정이라 재현된다.")


if __name__ == "__main__":
    main()
