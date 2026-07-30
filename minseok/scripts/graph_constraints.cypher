// 그래프 스키마 강제 — 라벨별 external_id 유니크 + 조회 템플릿용 인덱스.
//
// 스키마리스를 방치하지 않는다(neo4j-harness §3). external_id 는 PG 정본의 코드값이라
// 유니크 제약이 곧 엔티티 해소 장치다 — 같은 상권이 표기 차이로 두 노드가 되는 일이 없다.
// 전부 IF NOT EXISTS 라 몇 번 적용해도 같다(scripts/project_graph.py 가 매 실행 적용).
//
// 문장 구분은 세미콜론. project_graph.py 가 세미콜론으로 쪼개 하나씩 보낸다.

CREATE CONSTRAINT area_external_id IF NOT EXISTS
FOR (n:Area) REQUIRE n.external_id IS UNIQUE;

CREATE CONSTRAINT region_external_id IF NOT EXISTS
FOR (n:Region) REQUIRE n.external_id IS UNIQUE;

CREATE CONSTRAINT industry_external_id IF NOT EXISTS
FOR (n:Industry) REQUIRE n.external_id IS UNIQUE;

CREATE CONSTRAINT article_external_id IF NOT EXISTS
FOR (n:Article) REQUIRE n.external_id IS UNIQUE;

CREATE CONSTRAINT topic_external_id IF NOT EXISTS
FOR (n:Topic) REQUIRE n.external_id IS UNIQUE;

// 최신 기사 N건 조회(langgraph-harness §3-3 area_articles 템플릿)가 정렬에 쓴다.
CREATE INDEX article_published_at IF NOT EXISTS
FOR (n:Article) ON (n.published_at);
