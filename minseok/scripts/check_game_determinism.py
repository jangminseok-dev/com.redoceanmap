"""game 앱 결정론·경계 회귀 검사 (game-harness §8).

**grep을 쓰지 않는 이유:** 결정론 규칙을 설명하는 docstring에 `random`·`datetime.now`·
`hash()` 같은 단어가 필연적으로 등장한다. 1단계 실측에서 grep 오탐률이 100%였다
(3건 전부 주석). 오탐이 나는 검증은 결국 아무도 보지 않으므로 AST로 **실제 코드만** 본다.

실행:
    cd minseok && PYTHONPATH=apps python3 scripts/check_game_determinism.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

GAME_ROOT = Path(__file__).resolve().parent.parent / "apps" / "game"

# 현재 시각을 읽어도 되는 유일한 파일 — 도메인·유스케이스는 tick만 받는다(§1-1)
CLOCK_ADAPTER = "adapter/outbound/system_game_clock_adapter.py"

# 결정론을 깨는 호출 (§1-3)
BANNED_CALLS = {
    "hash": "내장 hash()는 PYTHONHASHSEED로 프로세스마다 달라진다",
    "uuid4": "uuid4는 엔트로피 의존이다",
}
BANNED_MODULES = {
    "random": "random 모듈은 쓰지 않는다 — blake2b 시드 유도만 허용(domain/rng/deterministic.py)",
    "yfinance": "실시세를 쓰지 않는다 — 주가는 전부 서버 생성 가상값(§2)",
}
# 스포크 직접 import 금지 (교차 협력은 허브 경유)
BANNED_SPOKES = {"market", "stock", "chat", "auth", "mail", "recommendation", "admin"}
TIME_CALLS = {"now", "utcnow", "today"}


def _attr_path(node: ast.AST) -> str:
    """`a.b.c` 형태 노드를 점 표기 문자열로."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _check(path: Path, rel: str) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    problems: list[str] = []

    for node in ast.walk(tree):
        # --- import 검사 ---
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            for name in names:
                root = name.split(".")[0]
                if root in BANNED_MODULES:
                    problems.append(f"{rel}:{node.lineno} {BANNED_MODULES[root]}")
                if root in BANNED_SPOKES:
                    problems.append(
                        f"{rel}:{node.lineno} 스포크 `{root}`를 직접 import했다 — 허브 포트를 쓴다"
                    )
            continue

        # --- 호출 검사 ---
        if not isinstance(node, ast.Call):
            continue
        func = node.func

        if isinstance(func, ast.Name) and func.id in BANNED_CALLS:
            problems.append(f"{rel}:{node.lineno} {BANNED_CALLS[func.id]}")

        if isinstance(func, ast.Attribute):
            dotted = _attr_path(func)
            if func.attr in BANNED_CALLS:
                problems.append(f"{rel}:{node.lineno} {BANNED_CALLS[func.attr]}")
            if dotted.startswith("random.") or dotted == "time.time":
                problems.append(f"{rel}:{node.lineno} `{dotted}` 호출 — 결정론 시드만 허용")
            if func.attr in TIME_CALLS and "datetime" in dotted and rel != CLOCK_ADAPTER:
                problems.append(
                    f"{rel}:{node.lineno} `{dotted}()` 호출 — 현재 시각은 {CLOCK_ADAPTER}만 읽는다"
                )

    return problems


def main() -> int:
    if not GAME_ROOT.exists():
        print(f"game 앱이 없다: {GAME_ROOT}")
        return 1

    problems: list[str] = []
    checked = 0
    for path in sorted(GAME_ROOT.rglob("*.py")):
        rel = path.relative_to(GAME_ROOT).as_posix()
        if rel.startswith("tests/"):
            continue  # 테스트는 재현성을 검증하려고 일부러 서브프로세스·시드를 다룬다
        checked += 1
        problems.extend(_check(path, rel))

    if problems:
        print(f"결정론·경계 위반 {len(problems)}건 (검사 {checked}파일)\n")
        for p in problems:
            print(f"  ✗ {p}")
        return 1

    print(f"결정론·경계 검사 통과 — {checked}개 파일, 위반 0건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
