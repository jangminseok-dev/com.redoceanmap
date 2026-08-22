"""구조화 로깅(③-M4) — LOG_FORMAT=json이면 전 로그를 한 줄 JSON으로 낸다.

운영(도커 stdout → docker logs·수집기)에서 필드 검색이 가능해지는 것이 목적이다.
로컬 dev 기본값은 plain(사람이 읽는 기존 포맷) — 켜는 쪽이 명시한다(prod compose).

- 한 줄 = 한 JSON 객체: ts(UTC ISO8601) · level · logger · message (+ exc, extra 필드).
- `logger.info("...", extra={"http": {...}})` 처럼 넘긴 extra는 최상위 필드로 편입된다
  (표준 LogRecord 속성과 겹치지 않는 키만 — JSON 직렬화 불가 값은 repr로 열화).
- uvicorn·uvicorn.error는 자체 핸들러를 비우고 루트로 전파시켜 같은 JSON 스트림에 싣는다.
  uvicorn.access는 **끈다** — main.py의 액세스 미들웨어(method·path·status·duration_ms)가
  대체한다(같은 요청을 두 줄로 찍지 않는다).
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

# LogRecord 기본 속성 — 이 밖의 키가 extra다(파이썬 logging 구현 관례)
_STANDARD_ATTRS = frozenset((
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename", "module",
    "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs",
    "relativeCreated", "thread", "threadName", "processName", "process", "taskName",
    "message", "asctime",
))


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _STANDARD_ATTRS or key.startswith("_"):
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = repr(value)  # 직렬화 불가 값은 버리지 않고 열화
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(log_format: str) -> None:
    """엔트리포인트(main·auth_main)가 앱 생성 전에 1회 호출한다."""
    if log_format != "json":
        return  # plain — uvicorn 기본 포맷 유지(로컬 dev 가독성)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    # uvicorn이 자체 핸들러로 이중 출력하지 않게 루트로 수렴시킨다
    for name in ("uvicorn", "uvicorn.error"):
        uv = logging.getLogger(name)
        uv.handlers = []
        uv.propagate = True
    # 액세스는 미들웨어가 대체 — uvicorn.access를 살려두면 같은 요청이 두 줄로 찍힌다
    access = logging.getLogger("uvicorn.access")
    access.handlers = []
    access.propagate = False
