"""결정론 난수 — blake2b 시드 유도 (game-harness §1-3).

같은 `(namespace, key)`는 언제·어디서·몇 번 물어도 같은 값이다. 이 성질이 깨지면 유저마다
다른 주가를 보게 되므로, 아래 셋을 쓰지 않는다.

- 내장 ``hash()`` — ``PYTHONHASHSEED``로 프로세스마다 달라진다(워커가 여러 개면 값이 갈린다)
- ``random`` 모듈 — 시드를 줘도 CPython 구현 안정성에 기대게 된다
- ``uuid4`` · ``time.time()`` — 시각·엔트로피 의존

에포크와 규칙 버전이 시드에 들어가므로, 시즌을 올리면(§1-4) 전 구간이 새 난수열이 된다.
"""
from __future__ import annotations

import math
from hashlib import blake2b

from game.domain.clock.game_epoch import GAME_EPOCH_ID, RULES_VERSION

_U64 = 1 << 64
_TWO_PI = 2.0 * math.pi


def u64(namespace: str, key: str) -> int:
    """64비트 정수 해시. 모든 결정론 값의 단일 출처."""
    seed = f"{GAME_EPOCH_ID}|{RULES_VERSION}|{namespace}|{key}".encode()
    return int.from_bytes(blake2b(seed, digest_size=8).digest(), "big")


def uniform(namespace: str, key: str) -> float:
    """[0, 1) 균등분포."""
    return u64(namespace, key) / _U64


def normal(namespace: str, key: str) -> float:
    """표준정규분포 — Box-Muller.

    독립인 균등난수 2개가 필요해 키에 접미사를 붙인다. 같은 키로 두 번 부르면 같은 값이다.
    """
    u1 = uniform(namespace, f"{key}#a")
    u2 = uniform(namespace, f"{key}#b")
    if u1 <= 0.0:  # 2^-64 확률. log 발산을 막는다
        u1 = 1.0 / _U64
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(_TWO_PI * u2)
