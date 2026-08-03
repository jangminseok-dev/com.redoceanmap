"""ORM 정의 ↔ alembic 마이그레이션 일치 검증.

불일치는 **배포 때 터진다.** admin이 이미 겪었다 — 컬럼이 없는 상태로 신코드가 뜨자
전 인증 요청이 500이 났고, "신코드 재기동 전에 alembic upgrade 먼저"가 그때 얻은 규칙이다.
여기서는 한 걸음 앞서 **정의 자체가 어긋났는지**를 잡는다.

game 테이블은 6·8단계에 3개가 더 들어온다. 그때도 이 테스트가 자동으로 걸린다.
"""
from __future__ import annotations

import ast
import importlib
import pathlib
import pkgutil

import game.adapter.outbound.orm as orm_package
from core.database import Base

# ORM 모듈을 손으로 나열하지 않는다 — 6단계에서 테이블 2개를 추가하며 여기 import를
# 빠뜨려 테스트가 "마이그레이션에만 있다"고 잘못 지적했다. 패키지를 순회하면 그 실수가 없다.
for _module in pkgutil.iter_modules(orm_package.__path__):
    importlib.import_module(f"{orm_package.__name__}.{_module.name}")

# FK 대상(`users.id`)을 import하지 않는다 — 스포크 직접 참조는 import-linter가 막는다.
# `ForeignKey("users.id")`는 문자열 참조라 컬럼 메타데이터를 읽는 데는 resolve가 필요 없다
# (실제로 계약 위반으로 한 번 걸린 뒤 확인했다).

# apps/game/tests/adapter/ → minseok/
_MINSEOK = pathlib.Path(__file__).resolve().parents[4]
_VERSIONS = _MINSEOK / "alembic" / "versions"


def _orm_columns() -> dict[str, dict[str, tuple[str, bool]]]:
    return {
        name: {c.name: (type(c.type).__name__, bool(c.nullable)) for c in table.columns}
        for name, table in Base.metadata.tables.items()
        if name.startswith("game_")
    }


def _column_spec(call: ast.Call) -> tuple[str, tuple[str, bool]]:
    """`sa.Column('이름', sa.타입, nullable=…)` 한 개를 (이름, (타입, nullable))로."""
    column_name = call.args[0].value
    # sa.String(8)처럼 인자를 받는 타입은 Call, sa.Integer처럼 아니면 Attribute다
    type_node = call.args[1]
    column_type = getattr(
        type_node.func if isinstance(type_node, ast.Call) else type_node, "attr", "?"
    )
    nullable = next((kw.value.value for kw in call.keywords if kw.arg == "nullable"), False)
    return column_name, (column_type, bool(nullable))


def _migration_columns() -> dict[str, dict[str, tuple[str, bool]]]:
    """`op.create_table('game_…')`와 `op.add_column('game_…', …)`을 AST로 읽는다.

    마이그레이션을 실행하지 않는다. **`add_column`도 읽어야 한다** — 컬럼을 나중에 덧댄
    테이블(레버리지 4개 등)이 create_table만 보면 ORM과 어긋난 것처럼 보인다.
    파일 이름순으로 훑으므로 리비전 순서대로 누적된다.
    """
    tables: dict[str, dict[str, tuple[str, bool]]] = {}
    for path in sorted(_VERSIONS.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            op_name = getattr(node.func, "attr", "")
            if op_name not in {"create_table", "add_column"}:
                continue
            if not (node.args and isinstance(node.args[0], ast.Constant)):
                continue
            table_name = node.args[0].value
            if not str(table_name).startswith("game_"):
                continue

            if op_name == "create_table":
                columns: dict[str, tuple[str, bool]] = {}
                for arg in node.args[1:]:
                    if isinstance(arg, ast.Call) and getattr(arg.func, "attr", "") == "Column":
                        name, spec = _column_spec(arg)
                        columns[name] = spec
                tables[table_name] = columns
            else:  # add_column — 이미 만들어진 테이블에 덧댄다
                target = node.args[1]
                if isinstance(target, ast.Call) and getattr(target.func, "attr", "") == "Column":
                    name, spec = _column_spec(target)
                    tables.setdefault(table_name, {})[name] = spec
    return tables


def test_게임_테이블이_ORM과_마이그레이션_양쪽에_있다():
    orm, migration = _orm_columns(), _migration_columns()
    assert orm, "game ORM이 하나도 없다"
    assert set(orm) == set(migration), (
        f"ORM에만 {set(orm) - set(migration)} · 마이그레이션에만 {set(migration) - set(orm)}"
    )


def test_컬럼_이름과_타입과_nullable이_일치한다():
    orm, migration = _orm_columns(), _migration_columns()
    for table in sorted(orm):
        assert set(orm[table]) == set(migration[table]), f"{table} 컬럼 목록 불일치"
        for column, spec in orm[table].items():
            assert spec == migration[table][column], (
                f"{table}.{column}: ORM {spec} ≠ 마이그레이션 {migration[table][column]}"
            )


def test_모든_게임_테이블은_int_단일_PK_id를_갖는다():
    """ENTITY_RULES — UUID·문자열·복합키 금지."""
    for name, table in Base.metadata.tables.items():
        if not name.startswith("game_"):
            continue
        primary = list(table.primary_key.columns)
        assert len(primary) == 1, f"{name}: 복합 키 금지"
        assert primary[0].name == "id", f"{name}: PK 컬럼명은 id여야 한다"
        assert type(primary[0].type).__name__ == "Integer", f"{name}: PK는 int여야 한다"
