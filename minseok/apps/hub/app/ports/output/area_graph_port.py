from __future__ import annotations

from abc import ABC, abstractmethod

from hub.app.dtos.area_graph_dto import AreaGraphInfo


class AreaGraphPort(ABC):
    """허브가 스포크에 위임하는 상권 그래프(Neo4j 투영) 조회 추상 — 구현은 market, 소비는 chat 비교 경로.

    정본은 PG이고 그래프는 파생본(project_graph.py, 매일 02:15)이다 — 여기서는 관계(이웃·업종 연결·기사 연결)만 읽는다.
    """

    @abstractmethod
    async def describe(self, trdar_code: int, service_code: str) -> AreaGraphInfo | None:
        """상권 노드가 그래프에 없거나 그래프가 죽어 있으면 None(비교는 그 행만 비운다)."""
        ...
