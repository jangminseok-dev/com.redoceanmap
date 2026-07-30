"""PG(market) → Neo4j 단방향 투영 — 관계 축만 옮긴다.

neo4j-strategy §4 1단계. **정본은 PG이고 그래프는 파생본**이라(neo4j-harness §4)
이 스크립트는 한 방향으로만 흐르고, 그래프에만 있는 사실을 만들지 않는다.
전량 `MERGE` 라 몇 번 돌려도 노드·관계 수가 같다(멱등) — 그래서 복구 절차가 곧 재실행이다.

**벡터는 옮기지 않는다.** `market_news_articles.embedding`(1024차원)은 pgvector에 남고,
그래프는 "무엇이 무엇과 이어져 있나"만 담는다(langgraph-harness §3-1 역할 분담).

라벨·관계는 langgraph-harness §3-2 목록으로 한정하며, 전부 PG 코드값의 결정적 투영이다
(LLM 호출 0회 — 정형 데이터를 LLM으로 다시 추출하지 않는다).

    Area(trade_area.code) -[:IN_REGION]->    Region(region.code)
    Region                -[:IN_REGION]->    Region          (parent_code 계층: 동→구→시)
    Area                  -[:HAS_INDUSTRY]-> Industry(service_category.code)
    Article(news id)      -[:ABOUT]->        Topic(area_tag)

실행 (백엔드 컨테이너 — 호스트에 파이썬 개발환경이 없다):
    python scripts/project_graph.py             # 최신 분기 기준 투영
    python scripts/project_graph.py --dry-run   # PG 집계만 세고 그래프는 건드리지 않음
    python scripts/project_graph.py --quarter all
"""

import argparse
import sys
from pathlib import Path

from neo4j import GraphDatabase
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]  # minseok
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))
from core.key.secret_manager import get_secret_manager  # noqa: E402

_secrets = get_secret_manager()

BATCH = 5_000
CONSTRAINTS = Path(__file__).with_name("graph_constraints.cypher")

# Topic 은 원래 LLM 추출 자리지만(langgraph-harness §3-2), area_tag 는 수집 스크립트가
# 관리하는 고정 키워드라 LLM 없이 결정적으로 넣는다. 나중에 본문에서 추출한 주제와
# 섞이지 않도록 출처를 접두어로 못박는다.
TOPIC_PREFIX = "area:"


def market_url() -> str:
    """market 전용 DB(:5434). 미설정 시 메인 DB 폴백은 core/config 와 같은 규칙."""
    url = _secrets.get("MARKET_DATABASE_URL") or _secrets.require("DATABASE_URL")
    return url.replace("postgresql://", "postgresql+psycopg://")


# --- PG 조회 (SELECT 전용 — 이 스크립트는 PG에 쓰지 않는다) ---------------------

SQL_REGIONS = "SELECT code, name FROM region"
SQL_REGION_PARENTS = "SELECT code, parent_code FROM region WHERE parent_code IS NOT NULL"
SQL_AREAS = "SELECT code, name, region_code FROM trade_area"
SQL_INDUSTRIES = "SELECT code, name FROM service_category"
SQL_ARTICLES = """
SELECT id, title, published_at, area_tag
FROM market_news_articles
"""
SQL_AREA_INDUSTRY_LATEST = """
SELECT DISTINCT trdar_code, service_code
FROM store
WHERE year_quarter = (SELECT max(year_quarter) FROM store)
"""
SQL_AREA_INDUSTRY_ALL = "SELECT DISTINCT trdar_code, service_code FROM store"


def fetch(engine, sql: str) -> list[dict]:
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(text(sql)).mappings()]


# --- 그래프 적재 (전량 MERGE) ---------------------------------------------------

MERGE_NODE = """
UNWIND $rows AS row
MERGE (n:{label} {{external_id: row.external_id}})
SET n += row.props
"""

MERGE_REL = """
UNWIND $rows AS row
MATCH (a:{src} {{external_id: row.src}})
MATCH (b:{dst} {{external_id: row.dst}})
MERGE (a)-[:{rel}]->(b)
"""


def run_batched(session, query: str, rows: list[dict], label: str) -> int:
    for start in range(0, len(rows), BATCH):
        session.run(query, rows=rows[start : start + BATCH])
    print(f"  {label:<34} {len(rows):>7,}")
    return len(rows)


def apply_constraints(session) -> None:
    statements = [s.strip() for s in CONSTRAINTS.read_text().split(";") if s.strip()]
    for stmt in statements:
        session.run(stmt)
    print(f"  제약·인덱스 적용 (IF NOT EXISTS)        {len(statements):>7,}")


def project(session, data: dict) -> None:
    print("노드")
    run_batched(
        session,
        MERGE_NODE.format(label="Region"),
        [
            {"external_id": r["code"], "props": {"name": r["name"]}}
            for r in data["regions"]
        ],
        "Region",
    )
    run_batched(
        session,
        MERGE_NODE.format(label="Area"),
        [
            {"external_id": str(a["code"]), "props": {"name": a["name"]}}
            for a in data["areas"]
        ],
        "Area",
    )
    run_batched(
        session,
        MERGE_NODE.format(label="Industry"),
        [
            {"external_id": i["code"], "props": {"name": i["name"]}}
            for i in data["industries"]
        ],
        "Industry",
    )
    run_batched(
        session,
        MERGE_NODE.format(label="Article"),
        [
            {
                "external_id": str(a["id"]),
                "props": {
                    "title": a["title"],
                    # 드라이버가 tz-aware datetime 을 그대로 넘긴다 — 문자열화하지 않는다
                    "published_at": a["published_at"],
                },
            }
            for a in data["articles"]
        ],
        "Article",
    )
    tags = sorted({a["area_tag"] for a in data["articles"] if a["area_tag"]})
    run_batched(
        session,
        MERGE_NODE.format(label="Topic"),
        [{"external_id": TOPIC_PREFIX + t, "props": {"name": t}} for t in tags],
        "Topic (area_tag 결정적 투영)",
    )

    print("관계")
    run_batched(
        session,
        MERGE_REL.format(src="Area", dst="Region", rel="IN_REGION"),
        [
            {"src": str(a["code"]), "dst": a["region_code"]}
            for a in data["areas"]
            if a["region_code"]
        ],
        "(:Area)-[:IN_REGION]->(:Region)",
    )
    run_batched(
        session,
        MERGE_REL.format(src="Region", dst="Region", rel="IN_REGION"),
        [{"src": r["code"], "dst": r["parent_code"]} for r in data["region_parents"]],
        "(:Region)-[:IN_REGION]->(:Region)",
    )
    run_batched(
        session,
        MERGE_REL.format(src="Area", dst="Industry", rel="HAS_INDUSTRY"),
        [
            {"src": str(p["trdar_code"]), "dst": p["service_code"]}
            for p in data["area_industry"]
        ],
        "(:Area)-[:HAS_INDUSTRY]->(:Industry)",
    )
    run_batched(
        session,
        MERGE_REL.format(src="Article", dst="Topic", rel="ABOUT"),
        [
            {"src": str(a["id"]), "dst": TOPIC_PREFIX + a["area_tag"]}
            for a in data["articles"]
            if a["area_tag"]
        ],
        "(:Article)-[:ABOUT]->(:Topic)",
    )


def report(session) -> None:
    print("그래프 현재 상태")
    for label in ["Area", "Region", "Industry", "Article", "Topic"]:
        n = session.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()["c"]
        print(f"  {label:<34} {n:>7,}")
    rels = session.run(
        "MATCH ()-[r]->() RETURN type(r) AS t, count(r) AS c ORDER BY t"
    ).data()
    for row in rels:
        print(f"  :{row['t']:<33} {row['c']:>7,}")


def main() -> None:
    parser = argparse.ArgumentParser(description="PG(market) → Neo4j 단방향 투영")
    parser.add_argument(
        "--quarter",
        choices=["latest", "all"],
        default="latest",
        help="HAS_INDUSTRY 산출 범위. latest=최신 분기의 상권×업종 조합만(기본)",
    )
    parser.add_argument("--dry-run", action="store_true", help="PG 집계만 출력")
    args = parser.parse_args()

    engine = create_engine(market_url(), pool_pre_ping=True)
    data = {
        "regions": fetch(engine, SQL_REGIONS),
        "region_parents": fetch(engine, SQL_REGION_PARENTS),
        "areas": fetch(engine, SQL_AREAS),
        "industries": fetch(engine, SQL_INDUSTRIES),
        "articles": fetch(engine, SQL_ARTICLES),
        "area_industry": fetch(
            engine,
            SQL_AREA_INDUSTRY_ALL if args.quarter == "all" else SQL_AREA_INDUSTRY_LATEST,
        ),
    }
    print(f"PG 조회 완료 (HAS_INDUSTRY 범위: {args.quarter})")
    for key, rows in data.items():
        print(f"  {key:<34} {len(rows):>7,}")

    if args.dry_run:
        print("\n--dry-run — 그래프는 건드리지 않았다")
        return

    driver = GraphDatabase.driver(
        _secrets.require("NEO4J_URI"),
        auth=(_secrets.get("NEO4J_USER", "neo4j"), _secrets.require("NEO4J_PASSWORD")),
    )
    driver.verify_connectivity()
    try:
        with driver.session(database="neo4j") as session:
            apply_constraints(session)
            project(session, data)
            report(session)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
