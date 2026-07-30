# DB 브라우저 — pgadmin · Neo4j Browser

내부 데이터를 눈으로 보는 두 창구. 둘 다 **127.0.0.1 루프백에만** 바인딩돼 있다(LAN 노출 없음).

관련: 루트 `CLAUDE.md` 명령어 절 · [[minseok/apps/market/_docs/CLAUDE|market CLAUDE]](앱 전용 DB)

---

## 원격(맥 등)에서 열 때 — SSH 터널

두 브라우저는 **백엔드 PC(WSL2)의 `127.0.0.1`에만** 바인딩돼 있다(루트 `CLAUDE.md`: 0.0.0.0 금지).
맥에서 `http://127.0.0.1:5050`을 열면 **맥 자신**을 가리키므로 아무것도 안 뜬다. SSH 터널이 정공법이다.

```bash
# 맥 터미널에서. 이 창은 켜둔 채로 둔다(-N = 셸 없이 터널만).
ssh -N -L 15050:127.0.0.1:5050 -L 17474:127.0.0.1:7474 -L 17687:127.0.0.1:7687 host@192.168.0.85
```

- 접속 주소는 **Windows 호스트 `192.168.0.85`** 다. WSL 내부 IP(`192.168.20.72`)로는 맥에서 닿지 않는다.
  Windows가 22번을 WSL로 넘겨주므로 SSH는 WSL 안에서 끝나고, `-L`의 `127.0.0.1`이 곧 WSL의 루프백이다.
- **로컬 포트를 1로 시작하는 번호로 어긋나게 잡는 이유**: VS Code Remote-SSH가 5050·7474·7687을
  이미 점유하고 있으면 `bind: Address already in use`로 터널이 안 선다. VS Code PORTS 탭에서
  Stop Forwarding 하면 원래 번호를 쓸 수 있다.

> **VS Code 자동 포워딩이 조용히 죽는다.** 세션이 오래되거나 컨테이너가 재시작되면 맥 쪽 리스너는
> 살아 있는데 채널만 끊긴다. 증상이 특이하다 — `curl`이 **연결은 되고 응답 0바이트로 타임아웃**
> (`Connected to 127.0.0.1` 뒤 `Operation timed out ... 0 bytes received`). 아무것도 안 듣고 있으면
> 즉시 `000`이 나므로, **멈추면 포워딩이 있는데 죽은 것**이다. PORTS 탭에서 지웠다 다시 잡거나
> 위처럼 다른 포트로 우회한다.

### Neo4j는 포트 두 개가 필요하다

7474만 열면 **화면은 뜨는데 로그인에서 막힌다.** UI는 7474에서 받아오지만 쿼리는
**클라이언트(맥 브라우저)가 직접** bolt로 붙기 때문이다. 위처럼 포트를 어긋나게 잡았다면
접속 화면의 **Connect URL을 `bolt://127.0.0.1:17687`로 직접 바꿔야 한다**(기본값은 7687).

---

## pgadmin — PostgreSQL(pgvector) 2개

| 항목 | 값 |
| --- | --- |
| 주소 | http://127.0.0.1:5050 |
| 로그인 | `.env`의 `PGADMIN_EMAIL` / `PGADMIN_PASSWORD` |
| 기동 | `docker compose --profile tools up -d pgadmin` |

로그인하면 서버 두 개가 이미 보인다. **둘을 섞지 않는 것이 이 프로젝트의 규칙이다**(앱 전용 DB 불가침).

| 서버 | 접속 | 무엇이 있나 |
| --- | --- | --- |
| `redoceanmap` | `redoceanmap-pgvector-1:5432` | 공유 DB — `users`·`news_articles`·`news_labels`·`price_bars`·`forecast_snapshots`·`fundamental_snapshots` |
| `market` | `market-pgvector:5432` | market 전용 DB — 상권 3NF(차원 5·팩트 9)·`market_news_articles`·`business_permits` |

**Host가 호스트 포트(5432/5434)가 아니라 컨테이너 이름인 이유**: pgadmin이 두 DB의 도커 네트워크
(`redoceanmap_default`·`market_default`)에 external로 붙어 있어 컨테이너 이름으로 직접 간다.
호스트에서 psql로 붙을 때는 반대로 포트를 쓴다 — 공유 `:5432`, market `:5434`.

서버 정의는 `_docs/pgadmin-servers.json`이 정본이고, **신규 설치일 때만** 자동 등록된다
(기존 볼륨 `pgadmin_data`에는 이미 등록돼 있어 무해). DB 비밀번호는 여기 넣지 않는다 —
최초 연결 때 한 번 입력하면 pgadmin이 보관한다.

> 2026-07-30까지 pgadmin은 어떤 compose에도 없이 수동 `docker run`으로만 떠 있었다.
> 이 PC를 다시 세팅하면 사라지는 상태였어서 compose(`profiles: ["tools"]`)로 편입했다.

### psql로 바로 볼 때

```bash
docker exec redoceanmap-pgvector-1 psql -U redocean -d redoceanmap   # 공유
docker exec market-pgvector psql -U market -d market                 # market
```

---

## Neo4j Browser — 그래프

**따로 설치할 것이 없다.** Neo4j 컨테이너에 브라우저가 내장돼 있다.

| 항목 | 값 |
| --- | --- |
| 주소 | http://127.0.0.1:7474 |
| 접속 URL | `bolt://127.0.0.1:7687` (브라우저 첫 화면에서 그대로 두면 된다) |
| 로그인 | `.env`의 `NEO4J_USER` / `NEO4J_PASSWORD` |
| 기동 | `docker compose --profile graph up -d neo4j` |

### 무엇이 들어 있나

`scripts/project_graph.py`(매일 02:15 cron)가 market DB에서 **단방향 투영**한 파생본이다.
정본은 PG이고 그래프에만 있는 사실은 만들지 않는다. 전량 `MERGE`라 재실행이 곧 복구다.
**벡터(임베딩)는 옮기지 않는다** — pgvector에 남고 그래프는 관계만 담는다.

```
Area(1,650)  -[:IN_REGION]->    Region(425)     상권 → 행정동
Region       -[:IN_REGION]->    Region          동 → 구 → 시 (자기참조 계층)
Area         -[:HAS_INDUSTRY]-> Industry(100)   상권 → 업종
Article(1,377) -[:ABOUT]->      Topic(30)       기사 → 지역 주제(area: 접두)
```

### 시작 쿼리

```cypher
// 전체 규모 — 라벨별 노드 수
MATCH (n) RETURN labels(n)[0] AS 라벨, count(*) AS 개수 ORDER BY 개수 DESC;

// 관계 종류별 개수
MATCH ()-[r]->() RETURN type(r) AS 관계, count(*) AS 개수 ORDER BY 개수 DESC;

// 특정 상권이 속한 행정동 → 자치구 (계층 타고 올라가기)
MATCH (a:Area {name: "성수동카페거리"})-[:IN_REGION*1..3]->(r:Region)
RETURN a.name, collect(r.name) AS 상위지역;

// 업종을 공유하는 이웃 상권 — SQL로는 어색하고 그래프가 자연스러운 2-hop 질의
MATCH (a:Area {name: "성수동카페거리"})-[:HAS_INDUSTRY]->(i:Industry)<-[:HAS_INDUSTRY]-(b:Area)
WHERE a <> b
RETURN b.name AS 비슷한상권, count(i) AS 공통업종수
ORDER BY 공통업종수 DESC LIMIT 10;

// 어떤 지역 주제에 기사가 몰려 있나
MATCH (ar:Article)-[:ABOUT]->(t:Topic)
RETURN t.name AS 주제, count(ar) AS 기사수 ORDER BY 기사수 DESC LIMIT 15;
```

> 마지막 2-hop 질의가 **현재 그래프의 유일한 실사용 후보**다. 2026-07-30 기준 백엔드에
> Neo4j를 읽는 코드는 0줄이고 cron이 투영만 하고 있다 — 그래프를 쓰는 기능(예: "비슷한 상권
> 추천")을 만들면 그때 허브 포트가 생긴다.

### cypher-shell로 바로 볼 때

```bash
docker exec redoceanmap-neo4j-1 cypher-shell -u <NEO4J_USER> -p <NEO4J_PASSWORD> \
  "MATCH (n) RETURN count(n);"
```
