"""웹훅 토큰 검증 — 운영 기동 거부 + 상수 시간 비교 회귀."""
import pytest
from fastapi import HTTPException

from hub.adapter.inbound.api.v1 import webhook_token
from hub.adapter.inbound.api.v1.webhook_token import require_token_in_production, verify_webhook_token


def test_운영에서_토큰이_비면_기동을_거부한다():
    for empty in (None, ""):
        with pytest.raises(RuntimeError):
            require_token_in_production("production", empty)


def test_개발에서는_토큰이_비어도_기동한다():
    require_token_in_production("development", None)
    require_token_in_production("production", "set")


def test_토큰이_다르거나_없으면_401(monkeypatch):
    monkeypatch.setattr(webhook_token, "N8N_INBOUND_TOKEN", "정답토큰")
    for bad in (None, "", "오답토큰"):
        with pytest.raises(HTTPException) as e:
            verify_webhook_token(bad)
        assert e.value.status_code == 401


def test_토큰이_맞으면_통과(monkeypatch):
    monkeypatch.setattr(webhook_token, "N8N_INBOUND_TOKEN", "정답토큰")
    verify_webhook_token("정답토큰")
