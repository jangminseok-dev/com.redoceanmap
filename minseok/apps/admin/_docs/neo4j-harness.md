# NEO4J-HARNESS — 그래프DB 운영 하네스

admin 앱 → [[minseok/apps/admin/_docs/CLAUDE|admin CLAUDE]] · 구조 하네스 → [[_docs/harness|harness]] ·
허브 인프라 소유 → [[minseok/apps/hub/_docs/CLAUDE|hub CLAUDE]]

**이 문서는 기능 설계서가 아니다.** 그래프DB를 "언제·누가·어떤 모양으로만" 쓸 수 있는지를 고정해,
스키마리스라는 이유로 아무 노드나 생기는 것을 막는 배선(harness)이다.
ROADMAP의 과설계 목록에 **"Neo4j 기능 설계(예약 폴더 채우기 금지)"**가 명시돼 있으므로,
그래프 코드를 새로 쓰기 전에 §5(도입 조건)를 먼저 통과해야 한다.

---

## 0. 현재 상태 (2026-07-27 기준 사실)

| 항목 | 상태 |
|---|---|
| 서버 | `docker-compose.yaml`의 `neo4j` 서비스 — 이미지 `neo4j:5`, `127.0.0.1:7474`(HTTP)·`127.0.0.1:7687`(Bolt), 볼륨 `neo4j_data`. **준비만 되어 있고 상시 기동 아님** |
| 인증 | `NEO4J_AUTH=${NEO4J_AUTH:-neo4j/please_change}` — 기본값이 그대로 쓰이면 안 된다(§5) |
| 클라이언트 | `minseok/requirements.txt`의 `neo4j-graphrag==1.18.0` (전이 의존 `neo4j` 드라이버 6.2.0) |
| 코드 | 그래프 접속 코드 **0건**. 자리만 예약됨 — `hub/adapter/outbound/graph/`(허브 소유 전역 인프라) |
| prod | ROADMAP ①-M2에서 **prod compose 제외**(미사용). 현재는 개발 스택 전용 |

---

## 1. 데이터 모델 — 그래프의 기본 단위

그래프 데이터는 **노드(node) · 라벨(label) · 관계(relationship) · 속성(property)** 으로 정의되며,
그중 **노드와 관계가 그래프를 구성하는 기본 단위**다.

| 요소 | 정의 | 예 |
|---|---|---|
| **노드(node)** | 엔티티 하나. 그래프 그림에서 동그라미로 그려지는 각각 | 사람 2명, 책 1권 = 노드 3개 |
| **라벨(label)** | 노드의 분류. 한 노드가 어떤 종류인지 식별 | `Person` 라벨 노드 2개, `Book` 라벨 노드 1개 |
| **관계(relationship)** | 두 노드를 연결하며, 화살표로 방향까지 표현 | `:HAS_READ`(사람→책, "읽었다"), `:IS_FRIENDS_WITH`(사람↔사람, "친구다") |
| **속성(property)** | 노드·관계에 붙는 설명. 각 개체를 식별·서술 | `Person.name`·`Person.age`, `:HAS_READ.on`(읽은 날짜) |

속성은 노드에만 붙는 것이 아니다. "언제 읽었는가"처럼 **두 개체 사이에서만 성립하는 사실**은
노드가 아니라 **관계의 속성**(`on`)으로 둔다 — 이 구분이 이 문서에서 가장 자주 위반되는 지점이다.

```cypher
// 위 정의를 그대로 옮긴 최소 예 — 노드 3 · 관계 3
CREATE (a:Person {name: '민석', age: 30})
CREATE (b:Person {name: '지연', age: 28})
CREATE (bk:Book   {title: 'Graph Databases'})
CREATE (a)-[:HAS_READ {on: date('2026-07-20')}]->(bk)   // 관계 속성 = 읽은 날짜
CREATE (b)-[:HAS_READ {on: date('2026-07-24')}]->(bk)
CREATE (a)-[:IS_FRIENDS_WITH]->(b)                       // 무방향 의미, 저장은 단방향 1개
```

## 2. 모델링 규칙 (위반 시 리뷰 반려)

1. **명명 고정** — 라벨 `PascalCase` 단수(`Person`, `Trdar`), 관계 `UPPER_SNAKE_CASE` 동사구
   (`HAS_READ`, `IS_FRIENDS_WITH`), 속성 `snake_case`. PG 테이블/컬럼명과 1:1로 베끼지 않는다
   (그래프는 관계 탐색용 모델이지 테이블 사본이 아니다).
2. **관계 방향은 한 번만 만든다** — 상호 관계(`IS_FRIENDS_WITH`)라도 양방향 2개를 만들지 않는다.
   조회에서 방향을 생략(`-[:IS_FRIENDS_WITH]-`)하면 되고, 2개를 만들면 중복 갱신 버그가 된다.
3. **속성 vs 노드 승격 기준** — 값이 (a) 다른 노드와 관계를 맺거나 (b) 그 자체로 검색 축이 되면
   노드로 승격, 아니면 속성으로 둔다. 애매하면 **속성으로 시작**한다(되돌리기가 싸다).
4. **자유 속성 금지** — 라벨별 허용 속성 집합을 이 문서의 표에 적고 나서 쓴다. 코드에서 임의 dict를
   그대로 `SET n += $props` 하지 않는다.
5. **식별자** — 모든 노드는 PG의 원본 키를 담는 속성 하나(`external_id` 등)를 갖고, 그 속성에
   유니크 제약을 건다(§3). Neo4j 내부 `elementId()`를 외부 식별자로 저장·노출하지 않는다.
6. **쓰기는 멱등** — 적재는 `CREATE`가 아니라 `MERGE` + 유니크 키 기준. 재실행이 중복 노드를 만들면
   그 스크립트는 잘못된 것이다.

## 3. 스키마 강제 — 제약·인덱스 (스키마리스를 방치하지 않는다)

그래프는 스키마가 없으므로, **제약(constraint)이 곧 하네스**다. 라벨을 새로 도입하는 커밋은
반드시 제약·인덱스 Cypher를 같은 커밋에 포함한다.

```cypher
CREATE CONSTRAINT person_ext_id IF NOT EXISTS FOR (p:Person) REQUIRE p.external_id IS UNIQUE;
CREATE CONSTRAINT book_ext_id   IF NOT EXISTS FOR (b:Book)   REQUIRE b.external_id IS UNIQUE;
CREATE INDEX     person_name    IF NOT EXISTS FOR (p:Person) ON (p.name);
SHOW CONSTRAINTS;  // 검증
```

- **Community 판 한계:** `neo4j:5` 이미지는 Community이므로 **속성 존재(NOT NULL)·타입·노드 키 제약은
  쓸 수 없다**(Enterprise 전용). 즉 "필수 속성"은 DB가 막아주지 않는다 —
  **pydantic 스키마 + 어댑터 검증이 그 자리를 대신**하며, 이건 선택이 아니라 보완 의무다.
- 제약 Cypher는 alembic이 관리하지 않는다(PG 전용). 별도 `.cypher` 파일로 버전 관리하고,
  적재 스크립트가 기동 시 `IF NOT EXISTS`로 멱등 적용한다.

## 4. 소유와 경계 — 스타 토폴로지 안에서의 그래프

| 규칙 | 내용 |
|---|---|
| 소유자 | 그래프는 **허브 소유 전역 인프라**다 → 접속 코드는 `hub/adapter/outbound/graph/`에만 둔다 |
| admin의 지위 | **소비자**. admin은 드라이버·Cypher를 직접 잡지 않고 허브 포트를 주입받는다(기존 슬라이스와 동일) |
| 스포크 | 스포크가 Bolt에 직접 붙는 것 금지 — 스포크↔스포크 우회 경로가 되어 스타가 메시로 무너진다 |
| 사실의 정본 | **PG가 정본(source of truth)**, 그래프는 관계 탐색용 파생본. 그래프에만 존재하는 사실을 만들지 않는다 |
| 이중 기록 | 같은 사실을 PG와 그래프에 각각 쓰는 코드 금지 — PG 커밋 후 **단방향 투영**(적재 스크립트/크론) 한 경로만 |
| 장애 격리 | 그래프가 죽어도 기존 API는 정상이어야 한다. 그래프 조회 실패는 500이 아니라 **해당 섹션 부재**로 처리 |
| 감사 | 어드민이 그래프에 **쓰기**를 하게 되면 `AuditLogPort`(`admin_audit_logs`) 기록 대상이다. 읽기 전용 조회는 기록하지 않는다(admin CLAUDE의 감사 원칙 그대로) |

## 5. 운영 규칙 — 접속·비밀값·백업

1. **비밀값은 `core/key/secret_manager.py` 경유** — `NEO4J_URI`·`NEO4J_USER`·`NEO4J_PASSWORD`를
   `.env.example`에 키로 등록하고, 런타임 상수는 `core/config.py`에 한 줄로 노출한다.
   코드에서 `os.getenv`·`load_dotenv` 재사용 금지(백엔드 비밀값 규칙).
2. **기본 비밀번호 사용 금지** — compose 기본값 `neo4j/please_change`가 실제로 쓰이는 상태에서
   기동하지 않는다. 최초 기동 전에 `.env`의 `NEO4J_AUTH`를 설정한다.
3. **포트는 루프백 유지** — `127.0.0.1:7474`·`127.0.0.1:7687`. `0.0.0.0` 바인딩 복귀 금지
   (근거·검증법 → [[minseok/apps/auth/_docs/bff-cloudflared-harness|bff-cloudflared-harness]] A.4).
4. **백업은 PG 백업과 별개다** — 기존 `pg_dump` 크론은 그래프를 담지 않는다. 그래프에 복구가 필요한
   사실을 두지 않는 것(§4 정본 규칙)이 1차 방어이며, 그럼에도 필요해지면
   `neo4j-admin database dump`를 별도 절차로 문서화하고 나서 도입한다.
5. **도입 조건(게이트)** — 아래를 모두 적고 나서 `graph/` 폴더에 첫 코드를 쓴다. 하나라도 비면 도입 보류다.
   - 그래프로만 답할 수 있는 질문 1개 이상(PG 조인으로 답이 되면 PG를 쓴다)
   - 라벨·관계·속성 목록과 그 제약 Cypher
   - PG→그래프 투영 경로(누가, 언제, 멱등한가)
   - 그래프가 죽었을 때의 응답 (§4 장애 격리)

## 6. 검증 명령

```bash
# 기동 (개발 스택 전용 — prod compose 제외 상태)
docker compose up -d neo4j
docker compose ps neo4j

# 서버 연결·버전 확인 (자격증명은 .env의 NEO4J_AUTH)
docker compose exec neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" \
  "CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition;"

# 제약 목록 — 라벨 도입 커밋마다 확인
docker compose exec neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "SHOW CONSTRAINTS;"

# 파이썬 드라이버 스모크 (백엔드 컨테이너에서)
docker exec redoceanmap-backend-1 python -c \
  "from neo4j import GraphDatabase; d=GraphDatabase.driver('bolt://neo4j:7687', auth=('neo4j','<pw>')); d.verify_connectivity(); print('ok')"

# 경계 검증 — 그래프 접속 코드가 허브 밖으로 샜는지
grep -rn --include="*.py" "GraphDatabase\|neo4j_graphrag" minseok/apps | grep -v "apps/hub/"   # 0줄이어야 한다
cd minseok && PYTHONPATH=apps lint-imports
```

## 7. 범위 밖 — 하지 않는다

| 항목 | 사유 |
|---|---|
| 예약 폴더 선(先)채우기 | ROADMAP 과설계 목록 명시. §5 게이트 통과 전 코드 금지 |
| PG 데이터의 그래프 전면 이관 | 정본은 PG. 그래프는 관계 탐색 파생본에 한정 |
| prod compose에 neo4j 편입 | ①-M2에서 명시적 제외(미사용). 실사용처가 생긴 뒤에 재검토 |
| GDS(그래프 알고리즘) 플러그인·Enterprise 기능 | Community 전제. 존재 제약·노드 키가 필요해지면 그건 PG로 푼다 |
| 그래프 전용 어드민 페이지 신설 | admin 6페이지 전면 구현은 과설계 목록. 필요 시 기존 data_source 카드 한 장으로 붙인다 |

## 8. 미해결 — 도입 전 확인할 것

- **버전 조합 미검증:** 서버 이미지 `neo4j:5`(부동 태그 — 최신 5.x로 흘러감) ↔ 파이썬 드라이버 6.2.0.
  `neo4j-graphrag`의 제약은 `neo4j>=5.17,<7`이라 설치는 되지만, **실서버 연결로 확인한 적이 없다**(§6 스모크).
  확인 후 이미지 태그를 `neo4j:5.26`처럼 **고정**한다 — requirements는 전부 핀 고정인데 이미지만 부동인 상태.
- **`.env.example`에 NEO4J 키 없음** — 현재 compose가 인라인 기본값에 의존한다(§5-1 위반 상태).
- **컨테이너 반영 필요** — `neo4j-graphrag`는 실행 중 백엔드 컨테이너에 수동 설치만 된 상태이며,
  이미지 재빌드 전까지 컨테이너 재생성 시 사라진다.
