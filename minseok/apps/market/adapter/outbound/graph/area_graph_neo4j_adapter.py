"""Neo4j 상권 그래프 읽기 어댑터 — project_graph.py가 투영한 관계만 읽는다(쓰지 않는다).

드라이버는 동기라 asyncio.to_thread로 감싼다. 그래프가 죽어 있거나 미설정이면 None — 비교표는 그 행만 비운다.
"""
from __future__ import annotations

import asyncio
import logging

from hub.app.dtos.area_graph_dto import AreaGraphInfo
from hub.app.ports.output.area_graph_port import AreaGraphPort

logger = logging.getLogger(__name__)

_Q = """
MATCH (a:Area {external_id: $code})
OPTIONAL MATCH p = (a)-[:IN_REGION*1..4]->(r:Region)
WITH a, [n IN nodes(p) WHERE n:Region | n.name] AS path
ORDER BY size(path) DESC
WITH a, head(collect(path)) AS region_path
OPTIONAL MATCH (a)-[:IN_REGION]->(dong:Region)<-[:IN_REGION]-(sib:Area)
WHERE sib <> a
WITH a, region_path, count(DISTINCT sib) AS siblings, dong
OPTIONAL MATCH (a)-[:HAS_INDUSTRY]->(i:Industry)
WITH a, region_path, siblings, dong, count(DISTINCT i) AS industries
OPTIONAL MATCH (a)-[:HAS_INDUSTRY]->(svc:Industry {external_id: $service})
WITH a, region_path, siblings, dong, industries, count(svc) > 0 AS has_service
OPTIONAL MATCH (dong)<-[:IN_REGION]-(rival:Area)-[:HAS_INDUSTRY]->(:Industry {external_id: $service})
WHERE rival <> a
WITH a, region_path, siblings, industries, has_service, count(DISTINCT rival) AS rivals
OPTIONAL MATCH (t:Topic)<-[:ABOUT]-(art:Article)
WHERE t.external_id STARTS WITH 'area:' AND size(replace(t.external_id, 'area:', '')) >= 2
  AND a.name CONTAINS replace(t.external_id, 'area:', '')
RETURN coalesce(region_path, []) AS region_path, siblings, industries, has_service, rivals,
       count(DISTINCT art) AS articles
"""


class AreaGraphNeo4jAdapter(AreaGraphPort):
    def __init__(self, uri: str, user: str, password: str) -> None:
        self._uri, self._user, self._password = uri, user, password
        self._driver = None

    def _connect(self):
        if self._driver is None:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(self._uri, auth=(self._user, self._password))
        return self._driver

    def _query(self, trdar_code: int, service_code: str) -> AreaGraphInfo | None:
        with self._connect().session() as session:
            rec = session.run(_Q, code=str(trdar_code), service=service_code).single()
        if rec is None:
            return None
        return AreaGraphInfo(
            trdar_code=trdar_code,
            region_path=tuple(rec["region_path"] or ()),
            sibling_area_count=int(rec["siblings"] or 0),
            industry_count=int(rec["industries"] or 0),
            has_service=bool(rec["has_service"]),
            same_service_sibling_count=int(rec["rivals"] or 0),
            article_count=int(rec["articles"] or 0),
        )

    async def describe(self, trdar_code: int, service_code: str) -> AreaGraphInfo | None:
        if not self._uri:
            return None
        try:
            return await asyncio.to_thread(self._query, trdar_code, service_code)
        except Exception:
            logger.warning("[market] 상권 그래프 조회 실패: %s", trdar_code, exc_info=True)
            return None
