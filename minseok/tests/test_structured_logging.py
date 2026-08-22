"""구조화 로깅(③-M4) 테스트 — 한 줄 JSON 계약과 extra·예외 편입을 고정한다."""
from __future__ import annotations

import json
import logging

from core.logging_setup import JsonLogFormatter, setup_logging


def _record(**kwargs) -> logging.LogRecord:
    record = logging.LogRecord(
        name="access", level=logging.INFO, pathname=__file__, lineno=1,
        msg=kwargs.pop("msg", "GET /stock 200"), args=kwargs.pop("args", ()), exc_info=None,
    )
    for key, value in kwargs.items():
        setattr(record, key, value)
    return record


def test_한_줄_유효_JSON에_기본_필드가_실린다():
    line = JsonLogFormatter().format(_record())
    assert "\n" not in line
    payload = json.loads(line)
    assert payload["level"] == "INFO" and payload["logger"] == "access"
    assert payload["message"] == "GET /stock 200"
    assert payload["ts"].endswith("+00:00")  # UTC 명시


def test_extra는_최상위_필드로_직렬화_불가_값은_repr로_열화():
    line = JsonLogFormatter().format(_record(
        http={"method": "GET", "status": 200, "duration_ms": 12.3},
        weird=object(),
    ))
    payload = json.loads(line)
    assert payload["http"] == {"method": "GET", "status": 200, "duration_ms": 12.3}
    assert payload["weird"].startswith("<object object")  # 버리지 않는다


def test_예외는_exc_필드에_스택으로_실린다():
    try:
        raise ValueError("터짐")
    except ValueError:
        import sys
        record = _record(msg="처리 실패")
        record.exc_info = sys.exc_info()
    payload = json.loads(JsonLogFormatter().format(record))
    assert "ValueError: 터짐" in payload["exc"]


def test_plain이면_로깅_구성을_건드리지_않는다():
    before = list(logging.getLogger().handlers)
    setup_logging("plain")
    assert logging.getLogger().handlers == before


def test_json이면_루트_수렴_액세스는_미들웨어가_대체(monkeypatch):
    root = logging.getLogger()
    saved = (list(root.handlers), root.level)
    try:
        setup_logging("json")
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JsonLogFormatter)
        assert logging.getLogger("uvicorn.error").propagate is True
        access = logging.getLogger("uvicorn.access")
        assert access.propagate is False and access.handlers == []
    finally:
        root.handlers, root.level = saved  # 다른 테스트의 로깅 구성 오염 방지
