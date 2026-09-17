from __future__ import annotations

from core.config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from hub.app.ports.output.area_graph_port import AreaGraphPort
from market.adapter.outbound.graph.area_graph_neo4j_adapter import AreaGraphNeo4jAdapter

_adapter: AreaGraphNeo4jAdapter | None = None


def get_area_graph_gateway() -> AreaGraphPort:
    """허브 AreaGraphPort 구현 프로바이더 — 드라이버는 프로세스당 하나(연결 풀)라 모듈 싱글턴."""
    global _adapter
    if _adapter is None:
        _adapter = AreaGraphNeo4jAdapter(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    return _adapter
