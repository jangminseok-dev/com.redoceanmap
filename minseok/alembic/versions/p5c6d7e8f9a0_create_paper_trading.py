"""AI 모의투자(paper) — 테이블 6개 생성 (GAME_SUNSET_PAPER_TRADING_PLAN_2026-09 3단계)

- paper_accounts: 참가 계정(exaone·signal 각 1행, user는 사용자당 1행). 현금이 여기 산다.
  AI 계정은 user_id NULL이라 (kind, user_id) 유니크에 안 걸린다 — 부분 유니크 인덱스로 kind당 1행을 막는다.
- paper_positions: 열린 포지션(청산되면 삭제). 이력은 trades가 맡는다.
- paper_trades: 체결 원장. decision_id가 있으면 AI 판단의 사후 체결, 없으면 사람 주문. reason·evidence는
  "왜 샀는가" 화면의 근거(인용 news_id·신호 키).
- paper_decisions: 계정당 하루 한 판단(프롬프트·원문 응답·주문·거부·후보 25종목 요약). (account, as_of)
  유니크가 step 재실행 멱등의 축.
- paper_decision_scores: 진입 주문의 5거래일 사후 채점 — 적중 정의는 forecast_snapshots 채점과 같다.
- paper_equity_daily: 일별 평가(자산 곡선). replayed=true는 2026-07-30 이후 리플레이 구간.

Revision ID: p5c6d7e8f9a0
Revises: o4b5c6d7e8f9
Create Date: 2026-09-08
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "p5c6d7e8f9a0"
down_revision: Union[str, Sequence[str], None] = "o4b5c6d7e8f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ts(name: str, nullable: bool = False):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _created():
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    op.create_table(
        "paper_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("cash_krw", sa.Float(), nullable=False),
        sa.Column("initial_cash_krw", sa.Float(), nullable=False),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("rules_version", sa.String(16), nullable=False),
        _created(),
        sa.UniqueConstraint("kind", "user_id", name="uq_paper_accounts_kind_user"),
    )
    op.create_index("ix_paper_accounts_user_id", "paper_accounts", ["user_id"])
    op.create_index("uq_paper_accounts_kind_ai", "paper_accounts", ["kind"], unique=True,
                    postgresql_where=sa.text("user_id IS NULL"))

    op.create_table(
        "paper_positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("side", sa.String(5), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("avg_price", sa.Float(), nullable=False),
        _ts("opened_at"),
        _created(),
        sa.UniqueConstraint("account_id", "ticker", "side", name="uq_paper_positions_account_ticker_side"),
    )
    op.create_index("ix_paper_positions_account_id", "paper_positions", ["account_id"])

    op.create_table(
        "paper_trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("side", sa.String(5), nullable=False),
        sa.Column("action", sa.String(5), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("fee_krw", sa.Float(), nullable=False),
        sa.Column("realized_pnl_krw", sa.Float(), nullable=True),
        _ts("ts"),
        sa.Column("decision_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("evidence", JSONB(), nullable=True),
        sa.Column("replayed", sa.Boolean(), nullable=False, server_default=sa.false()),
        _created(),
    )
    for col in ("account_id", "ticker", "ts", "decision_id"):
        op.create_index(f"ix_paper_trades_{col}", "paper_trades", [col])

    op.create_table(
        "paper_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        _ts("as_of"),
        sa.Column("model", sa.String(40), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("response_raw", sa.Text(), nullable=False),
        sa.Column("market_view", sa.Text(), nullable=False),
        sa.Column("orders", JSONB(), nullable=False),
        sa.Column("rejected", JSONB(), nullable=False),
        sa.Column("candidates", JSONB(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("replayed", sa.Boolean(), nullable=False, server_default=sa.false()),
        _ts("filled_at", nullable=True),
        _ts("scored_at", nullable=True),
        _created(),
        sa.UniqueConstraint("account_id", "as_of", name="uq_paper_decisions_account_as_of"),
    )
    op.create_index("ix_paper_decisions_account_id", "paper_decisions", ["account_id"])
    op.create_index("ix_paper_decisions_as_of", "paper_decisions", ["as_of"])

    op.create_table(
        "paper_decision_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("decision_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("action", sa.String(5), nullable=False),
        sa.Column("reason_kind", sa.String(12), nullable=False),
        sa.Column("realized_return_pct", sa.Float(), nullable=False),
        sa.Column("hit", sa.Boolean(), nullable=False),
        _ts("evaluated_at"),
        _created(),
        sa.UniqueConstraint("decision_id", "ticker", name="uq_paper_decision_scores_decision_ticker"),
    )
    op.create_index("ix_paper_decision_scores_decision_id", "paper_decision_scores", ["decision_id"])

    op.create_table(
        "paper_equity_daily",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("cash_krw", sa.Float(), nullable=False),
        sa.Column("positions_value_krw", sa.Float(), nullable=False),
        sa.Column("equity_krw", sa.Float(), nullable=False),
        sa.Column("replayed", sa.Boolean(), nullable=False, server_default=sa.false()),
        _created(),
        sa.UniqueConstraint("account_id", "as_of", name="uq_paper_equity_daily_account_as_of"),
    )
    op.create_index("ix_paper_equity_daily_account_id", "paper_equity_daily", ["account_id"])


def downgrade() -> None:
    for table in ("paper_equity_daily", "paper_decision_scores", "paper_decisions", "paper_trades",
                  "paper_positions", "paper_accounts"):
        op.drop_table(table)
