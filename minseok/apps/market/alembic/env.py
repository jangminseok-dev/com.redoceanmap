import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# minseok/ 와 minseok/apps 를 경로에 올려 core.* 및 market ORM을 import 가능하게 한다.
_MINSEOK = Path(__file__).parents[3]
sys.path.insert(0, str(_MINSEOK / "apps"))
sys.path.insert(0, str(_MINSEOK))

# core.config가 임포트 시점에 DATABASE_URL을 요구하므로 선로드 (루트 .env — 전역 관리자 경유)
from core.key.secret_manager import get_secret_manager  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
# market 독립 체인은 **market 전용 DB(:5434)**를 대상으로 한다 — DATABASE_URL(메인 DB)을
# 쓰면 이 체인이 엉뚱한 DB에 적용된다. 미설정 시 메인 폴백은 런타임·배치와 동일 규칙.
# 드라이버 접두사는 두 분기 모두에 붙여야 한다(psycopg2를 찾다 죽는 것을 방지).
_secrets = get_secret_manager()
config.set_main_option(
    "sqlalchemy.url",
    (_secrets.get("MARKET_DATABASE_URL") or _secrets.require("DATABASE_URL"))
    .replace("postgresql://", "postgresql+psycopg://"),
)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# market ORM만 등록 — 다른 앱(auth/chat/...) 테이블이 market DB에 새지 않게 한다.
from core.database import Base
import market.adapter.outbound.orm.region_orm  # noqa: F401
import market.adapter.outbound.orm.trade_area_division_orm  # noqa: F401
import market.adapter.outbound.orm.service_category_orm  # noqa: F401
import market.adapter.outbound.orm.change_indicator_orm  # noqa: F401
import market.adapter.outbound.orm.trade_area_orm  # noqa: F401
import market.adapter.outbound.orm.estimated_sales_orm  # noqa: F401
import market.adapter.outbound.orm.store_orm  # noqa: F401
import market.adapter.outbound.orm.floating_population_orm  # noqa: F401
import market.adapter.outbound.orm.resident_population_orm  # noqa: F401
import market.adapter.outbound.orm.working_population_orm  # noqa: F401
import market.adapter.outbound.orm.consumption_orm  # noqa: F401
import market.adapter.outbound.orm.apartment_orm  # noqa: F401
import market.adapter.outbound.orm.commercial_change_orm  # noqa: F401
import market.adapter.outbound.orm.commercial_change_benchmark_orm  # noqa: F401
import market.adapter.outbound.orm.market_news_article_orm  # noqa: F401
import market.adapter.outbound.orm.area_backtest_report_orm  # noqa: F401
import market.adapter.outbound.orm.commercial_trade_orm  # noqa: F401
import market.adapter.outbound.orm.franchise_industry_cost_orm  # noqa: F401

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
