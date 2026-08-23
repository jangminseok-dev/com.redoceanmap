import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# minseok/ 와 minseok/apps 를 경로에 올려 core.* 및 앱 ORM(chat, market...)을 import 가능하게 한다.
# (main.py 의 sys.path.insert(0, "apps") 와 동일 맥락 — 도커 백엔드의 자동 alembic 실행 포함)
_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(_ROOT / "apps"))
sys.path.insert(0, str(_ROOT))

from core.key.secret_manager import get_secret_manager  # noqa: E402

config = context.config
config.set_main_option(
    "sqlalchemy.url",
    get_secret_manager().require("DATABASE_URL").replace(
        "postgresql://", "postgresql+psycopg://"
    ),
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from core.database import Base
import auth.adapter.outbound.orm.user_orm  # noqa: F401
import auth.adapter.outbound.orm.refresh_token_orm  # noqa: F401
import auth.adapter.outbound.orm.rbac_orm  # noqa: F401
import admin.adapter.outbound.orm.audit_log_orm  # noqa: F401
import admin.adapter.outbound.orm.pdf_document_orm  # noqa: F401
# market ORM은 등록하지 않는다 — market은 전용 DB(:5434, apps/market/alembic 독립 체인)로
# 이전됨(루트 체인 market 부분 동결). 메인 DB에 남은 market 테이블 사본은 아래
# include_name 필터로 오토젠에서 제외한다(사본 drop 후 필터도 함께 제거할 것).
import chat.adapter.outbound.orm.conversation_orm  # noqa: F401
import recommendation.adapter.outbound.orm.recommendation_orm  # noqa: F401
import recommendation.adapter.outbound.orm.profile_orm  # noqa: F401
import recommendation.adapter.outbound.orm.alert_orm  # noqa: F401
import stock.adapter.outbound.orm.news_article_orm  # noqa: F401
import stock.adapter.outbound.orm.price_bar_orm  # noqa: F401
import stock.adapter.outbound.orm.news_label_orm  # noqa: F401
import stock.adapter.outbound.orm.fundamental_snapshot_orm  # noqa: F401
import stock.adapter.outbound.orm.news_event_study_report_orm  # noqa: F401
import stock.adapter.outbound.orm.disclosure_chunk_orm  # noqa: F401
import mail.adapter.outbound.orm.inbound_mail_orm  # noqa: F401
import hub.adapter.outbound.orm.langchain_session_orm  # noqa: F401
import game.adapter.outbound.orm.game_wallet_orm  # noqa: F401
import game.adapter.outbound.orm.game_position_orm  # noqa: F401
import game.adapter.outbound.orm.game_ledger_orm  # noqa: F401
import game.adapter.outbound.orm.game_store_orm  # noqa: F401
import game.adapter.outbound.orm.game_store_decision_orm  # noqa: F401
import game.adapter.outbound.orm.game_quarter_settlement_orm  # noqa: F401
import game.adapter.outbound.orm.game_limit_order_orm  # noqa: F401

target_metadata = Base.metadata

# 메인 DB에 남아 있는 market 테이블 사본(이관 후 롤백 안전용 보존) — metadata에서 market이
# 빠졌으므로 필터 없이 오토젠하면 전부 drop_table 후보로 잡힌다. 사본을 삭제하는 날 이
# 집합과 include_name 배선도 함께 제거한다.
_FROZEN_MARKET_TABLES = {
    "region", "trade_area_division", "service_category", "change_indicator", "trade_area",
    "estimated_sales", "store", "floating_population", "resident_population",
    "working_population", "consumption", "apartment", "commercial_change",
    "commercial_change_benchmark", "market_news_articles", "area_score_backtest_reports",
}


def _include_name(name, type_, parent_names) -> bool:
    if type_ == "table":
        return name not in _FROZEN_MARKET_TABLES
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_name=_include_name,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata,
            include_name=_include_name,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
