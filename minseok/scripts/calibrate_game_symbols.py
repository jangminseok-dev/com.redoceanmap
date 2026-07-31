"""게임 종목 파라미터 캘리브레이션 — price_bars(1d) → symbol_params.py.

game 앱은 런타임에 DB를 읽지 않는다(game-harness §3-2). 봉이 하루 갱신될 때마다 σ가 미세하게
바뀌면 **과거 주가 전 구간이 소급 변조**되기 때문이다. 그래서 이 스크립트가 오프라인에서
값을 뽑아 도메인 상수 파일로 굽는다.

**익명화가 이 스크립트의 책임이다.** 실 티커는 여기서만 보이고 출력에는 남지 않는다 —
σ 분포만 가져와 게임 종목 슬롯에 오름차순으로 배정한다. 가상 사명·업종·기준가는 게임이
정한 고정값이라 실제 기업과 대응 관계가 없다.

실행:
    # 실 DB에 붙는 스크립트라 --network host가 필요하다(DATABASE_URL이 localhost:5432)
    docker run --rm --network host -v <repo>:/work -w /work \
      -e PYTHONPATH=/work/minseok:/work/minseok/apps \
      minseok97/redoceanmap-backend:latest python minseok/scripts/calibrate_game_symbols.py

    python minseok/scripts/calibrate_game_symbols.py --dry-run   # 계산만, 파일 미수정

실행 후 반드시:
    1. symbol_params.py의 CALIBRATED_AT이 채워졌는지 확인
    2. game_epoch.py의 GAME_EPOCH_ID를 올린다(§1-4) — 안 올리면 진행 중 시즌의 과거가 바뀐다
"""
from __future__ import annotations

import argparse
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps"))

from core.key.secret_manager import get_secret_manager  # noqa: E402
from game.domain.market.symbol_params import (  # noqa: E402
    MU_CLIP,
    SIGMA_CLIP_MAX,
    SIGMA_CLIP_MIN,
    SYMBOLS,
)

MIN_BARS = 120  # 이보다 짧은 종목은 σ 추정이 불안정하다


def _fetch_daily_returns(dsn: str) -> dict[str, list[float]]:
    """티커별 일간 로그수익률. 지수(SPY·^VIX)는 종목이 아니라 제외한다."""
    query = """
        SELECT ticker, ts, close
        FROM price_bars
        WHERE timeframe = '1d' AND close > 0
        ORDER BY ticker, ts
    """
    closes: dict[str, list[float]] = defaultdict(list)
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(query)
        for ticker, _ts, close in cur:
            if ticker in ("SPY", "^VIX"):
                continue
            closes[ticker].append(float(close))

    returns: dict[str, list[float]] = {}
    for ticker, series in closes.items():
        if len(series) < MIN_BARS:
            continue
        returns[ticker] = [
            math.log(series[i] / series[i - 1]) for i in range(1, len(series))
        ]
    return returns


def _calibrate(returns: dict[str, list[float]]) -> list[tuple[float, float]]:
    """티커별 (σ, μ)를 클리핑해 σ 오름차순으로 정렬 — 여기서 티커 이름이 사라진다."""
    stats = [
        (
            min(max(statistics.pstdev(r), SIGMA_CLIP_MIN), SIGMA_CLIP_MAX),
            min(max(statistics.fmean(r), -MU_CLIP), MU_CLIP),
        )
        for r in returns.values()
    ]
    return sorted(stats)


def _pick_slots(stats: list[tuple[float, float]], count: int) -> list[tuple[float, float]]:
    """σ 분위수를 균등 분할해 대표 `count`개를 뽑는다(저·중·고변동이 고르게 섞이도록)."""
    if len(stats) < count:
        raise SystemExit(f"종목이 부족하다: {len(stats)}개 < {count}개")
    step = len(stats) / count
    return [stats[min(int(i * step), len(stats) - 1)] for i in range(count)]


def _center(mus: list[float]) -> list[float]:
    """μ를 평균 0으로 중심화한다.

    ⚠️ 이걸 안 하면 우상향 종목을 사서 방치하는 것이 유일한 최적 전략이 되어 게임이
    성립하지 않는다(game-strategy §3-1).
    """
    offset = statistics.fmean(mus)
    return [m - offset for m in mus]


def _render(slots: list[tuple[float, float]], mus: list[float]) -> str:
    lines = []
    for params, (sigma, _), mu in zip(SYMBOLS, slots, mus, strict=True):
        lines.append(
            f'    SymbolParams("{params.symbol}", "{params.name}", "{params.sector}", '
            f"{params.base_price_krw:_}, {sigma:.4f}, {mu:+.5f}),"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="게임 종목 σ·μ 캘리브레이션")
    parser.add_argument("--dry-run", action="store_true", help="계산 결과만 출력")
    args = parser.parse_args()

    dsn = get_secret_manager().require("DATABASE_URL").replace("postgresql+psycopg", "postgresql")
    returns = _fetch_daily_returns(dsn)
    print(f"대상 종목 {len(returns)}개 (봉 {MIN_BARS}개 이상)")

    slots = _pick_slots(_calibrate(returns), len(SYMBOLS))
    mus = _center([mu for _, mu in slots])

    print(f"\nCALIBRATED_AT = \"{datetime.now(timezone.utc).isoformat()}\"")
    print("SYMBOLS = (")
    print(_render(slots, mus))
    print(")")
    print(f"\nμ 합계 = {sum(mus):+.8f} (0이어야 한다)")

    if args.dry_run:
        return
    print(
        "\n위 블록을 apps/game/domain/market/symbol_params.py에 옮기고 "
        "CALIBRATED_AT을 채운 뒤, game_epoch.py의 GAME_EPOCH_ID를 올린다."
    )


if __name__ == "__main__":
    main()
