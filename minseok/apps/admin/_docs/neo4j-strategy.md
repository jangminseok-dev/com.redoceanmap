# NEO4J-STRATEGY — 도커 설치·기동 전략

admin 앱 → [[minseok/apps/admin/_docs/CLAUDE|admin CLAUDE]] ·
운영 규칙(선행 필독) → [[minseok/apps/admin/_docs/neo4j-harness|neo4j-harness]] ·
수요처 → [[minseok/apps/admin/_docs/langgraph-harness|langgraph-harness]] ·
허브 인프라 소유 → [[minseok/apps/hub/_docs/CLAUDE|hub CLAUDE]]

**역할 분담:** *무엇을 그래프에 담아도 되는가*는 neo4j-harness, *왜 그래프가 필요한가*는
langgraph-harness §3이 정한다. **이 문서는 "어느 스택에 · 어떤 자원으로 · 어떤 순서로 올리는가"
하나만** 다룬다. 컨테이너를 띄우는 것은 그래프 도입 게이트(neo4j-harness §5-5)와 별개다 —
**서버가 떠 있어도 접속 코드는 게이트 통과 전까지 0건을 유지한다.**

> 이 파일에는 원래 neo4j-harness의 사본이 들어 있었다(내용 중복). 2026-07-28에 도커 설치
> 전략으로 교체했다 — 운영 규칙이 필요하면 harness 쪽을 본다.

---

## 0. 실측한 현재 상태 (2026-07-28) — 함정 3개

`docker ps` · `docker volume ls` · `free -h`로 확인한 사실이다. neo4j 컨테이너는 **떠 있지 않고,
로컬에 neo4j 이미지도 없다**.

### 함정 ① 서비스가 **틀린 스택**에 정의돼 있다

| 스택 | compose | 상태 |
|---|---|---|
| **구 스택 = 실운영** | `/home/host/projects/redoceanmap/docker-compose.yaml` | backend·auth·redis·pgvector·cloudflared 가동 중. 네트워크 `redoceanmap_default`. **neo4j 서비스 없음** |
| 리포 스택 | `com.redoceanmap/docker-compose.yaml` | **neo4j 서비스는 여기에만 있다.** 이 스택은 컨테이너 0개(미가동) |

→ 리포에서 `docker compose up -d neo4j`를 하면 컨테이너는 `comredoceanmap_default`에 뜨고,
**백엔드(`redoceanmap_default`)는 `neo4j`라는 이름을 해석하지 못한다.**
neo4j-harness §6의 스모크 명령(`docker exec redoceanmap-backend-1 ... bolt://neo4j:7687`)은
**지금 그대로 실행하면 실패한다** — 문서가 틀린 것이 아니라 스택 배치가 안 끝난 것이다.

### 함정 ② 볼륨이 이미 초기화돼 있다 (비밀번호가 굳었다)

```
comredoceanmap_neo4j_data   516 MB   dbms/auth.ini · databases/{neo4j,system} · server_id(2026-07-06)
redoceanmap_neo4j_data      비어 있음
```

`NEO4J_AUTH`는 **데이터 디렉토리가 빈 최초 기동에만 적용된다.** 위 볼륨은 2026-07-06에
`neo4j/please_change`로 초기화된 상태이며, 지금 `.env`를 고쳐도 **비밀번호는 바뀌지 않는다**
(구 스택 `.env:32`의 주석이 이미 이 사실을 적어뒀다 — 그런데 정작 구 스택 compose에는 neo4j
서비스가 없다. 드리프트).
neo4j-harness §5-2가 금지한 "기본 비밀번호로 기동"이 **볼륨에 이미 박혀 있는 상태**다.

### 함정 ③ 이미지 태그가 부동이다

`neo4j:5`는 최신 5.x로 흘러간다. 로컬에 이미지가 없으므로 첫 기동은 오늘자 5.x를 받아온다 —
requirements는 전량 `==` 핀 고정인데 인프라 이미지만 부동인 불일치(neo4j-harness §8).

### 자원 실측 — 이게 설계 제약이다

| 항목 | 실측 |
|---|---|
| WSL2 메모리 | total **10 GiB** · available **7.1 GiB** · swap 3 GiB 중 **732 MiB 이미 사용** |
| 가동 컨테이너 8개 합계 | 약 1.47 GiB (backend 696 MiB가 최대) |
| 호스트 Ollama | `active` — EXAONE 7.8B 추론이 같은 10 GiB를 나눠 쓴다 |
| 디스크 | `/var/lib/docker` 864 GB 여유 — **디스크는 제약이 아니다** |

**Neo4j를 기본값으로 띄우면 안 되는 이유가 여기 있다.** JVM 힙 기본값은 RAM의 약 1/4(≈2.5 GiB),
페이지 캐시는 남은 메모리에서 자동 산정된다 — 합치면 수 GiB를 예약해 EXAONE 추론과 정면 충돌한다.
§3에서 힙·캐시를 **명시 고정**하는 것이 이 전략의 핵심이다.

---

## 1. 전략 결정 4개

| # | 결정 | 기각한 대안과 이유 |
|---|---|---|
| 1 | **구 스택 compose에 neo4j 서비스를 정의**한다(리포 compose의 정의는 개발용으로 유지) | `docker network connect`로 잇기 → **컨테이너 재생성 시 유실**된다(프론트 컨테이너에서 이미 겪은 함정, dual-stack 메모). redis를 구 스택에 추가한 2026-07-20 선례와 같은 방식 |
| 2 | **기존 볼륨 `comredoceanmap_neo4j_data`(516 MB)는 버린다** | 비밀번호를 되살릴 이유가 없다. 그래프는 PG의 파생본이라 **복구 대상이 아니다**(neo4j-harness §4·§5-4) — 재투영이 곧 복구다. 폐기가 싼 것이 이 인프라의 성질이고, 그래서 백업 절차도 만들지 않는다 |
| 3 | 태그를 **`neo4j:5.26`(5.x LTS)로 고정** | 부동 `neo4j:5`는 어느 날 스토어 포맷이 올라가도 조용히 따라간다. 드라이버(6.2.0)와의 조합은 §5-0 스모크로 확인하고 나서 확정 |
| 4 | **`profiles: ["graph"]`로 선택 기동**, backend의 `depends_on`에 넣지 않는다 | 상시 기동은 아직 근거가 없다(실사용처 0건). `depends_on`을 걸면 그래프 장애가 백엔드 장애가 되어 **장애 격리 원칙(neo4j-harness §4)을 compose가 위반**한다 |

---

## 2. 넣을 compose 서비스 (구 스택)

`/home/host/projects/redoceanmap/docker-compose.yaml`의 `pgvector` 아래에 붙이고,
`volumes:` 목록에 `neo4j_data:` 한 줄을 추가한다.

```yaml
  neo4j:
    image: neo4j:5.26                      # LTS 고정 — 부동 태그 금지(§1-3)
    profiles: ["graph"]                    # 기본 up -d 에서는 뜨지 않는다(§1-4)
    ports:
      - "127.0.0.1:7474:7474"              # HTTP(브라우저) — 루프백 유지
      - "127.0.0.1:7687:7687"              # Bolt(드라이버) — 루프백 유지
    volumes:
      - neo4j_data:/data
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD:?NEO4J_PASSWORD 미설정}   # 기본값 금지 — 없으면 기동 실패
      # --- 메모리 고정: 자동 산정에 맡기면 EXAONE과 충돌한다(§0 자원 실측) ---
      - NEO4J_server_memory_heap_initial__size=512m
      - NEO4J_server_memory_heap_max__size=512m
      - NEO4J_server_memory_pagecache_size=512m
      # --- 폭주 쿼리 차단: 클라이언트 타임아웃을 믿지 않고 서버에서 끊는다 ---
      - NEO4J_db_transaction_timeout=5s
    mem_limit: 1500m                       # 힙+캐시+JVM 오버헤드 상한(하드 캡)
    healthcheck:
      test: ["CMD-SHELL", "cypher-shell -u neo4j -p \"$$NEO4J_PASSWORD_HC\" 'RETURN 1' || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 40s
    restart: unless-stopped
```

| 항목 | 근거 |
|---|---|
| 힙 512m 고정 | 노드 수십만 규모의 이웃 확장 질의에는 과하지 않다. 부족하면 **늘리기 전에 쿼리를 고친다**(§3-3 화이트리스트라 쿼리가 유한하다) |
| 페이지캐시 512m | 그래프 크기 = PG 파생본 일부(상권·업종·지역·기사 노드). 전량 캐시를 노리지 않는다 |
| `mem_limit 1500m` | 남은 available 7.1 GiB 중 그래프 몫을 **명시적으로 1.5 GiB로 상한**. 초과 시 컨테이너만 죽고 추론은 산다 |
| `db.transaction.timeout=5s` | langgraph-harness §3-3이 요구한 타임아웃을 **서버에서** 강제. 어댑터 버그로 상한 없는 질의가 나가도 5초에 끊긴다 |
| 플러그인 없음 | APOC·GDS 미설치(neo4j-harness §7). `NEO4J_PLUGINS`를 쓰지 않는다 |
| `restart: unless-stopped` | 뜬 뒤에는 재부팅에도 살아야 한다. 다만 `profiles` 때문에 **한 번 올린 뒤에만** 적용된다 |

> `NEO4J_PASSWORD_HC`는 헬스체크가 컨테이너 안에서 읽을 값이라 별도 주입이 필요하다.
> 단순화하려면 헬스체크를 `wget -qO- localhost:7474 || exit 1`로 바꿔도 된다 —
> **첫 기동 때 실제로 통과하는 쪽을 확인하고 하나만 남긴다**(§5-0 완료 판정에 포함).

**리포 compose(`com.redoceanmap/docker-compose.yaml`)의 neo4j도 같은 값으로 맞춘다.**
두 파일이 갈라지면 맥·다른 머신에서 다른 설정으로 뜬다.

---

## 3. 자격증명 전략

1. **비밀값은 `NEO4J_PASSWORD` 하나로 수렴**시키고 `NEO4J_AUTH`는 그것을 조립해 쓴다(위 compose).
   키를 두 벌 관리하면 §0 함정 ②가 반복된다.
2. **양쪽 `.env`에 넣는다** — 구 스택 `.env`와 리포 `.env`는 별개 파일이다(dual-stack 규칙).
   구 스택 `.env:33`의 `NEO4J_AUTH=neo4j/please_change`는 **삭제하고** `NEO4J_PASSWORD`로 대체한다.
3. **`.env.example`에 키를 등록**한다 — `NEO4J_URI` · `NEO4J_USER` · `NEO4J_PASSWORD`.
   neo4j-harness §8의 "`.env.example`에 NEO4J 키 없음"이 이 단계에서 해소된다.
   런타임 상수는 `core/config.py` 한 줄, 조회는 `core/key/secret_manager.py` 경유(백엔드 비밀값 규칙).
4. **비밀번호는 볼륨 초기화 시점에만 박힌다.** 나중에 바꿀 때 `.env` 수정은 **무효**이고,
   `cypher-shell`에서 `ALTER CURRENT USER SET PASSWORD FROM '옛것' TO '새것'`을 쓴다
   (또는 볼륨을 버리고 다시 만든다 — 파생본이라 그래도 된다).
5. **접속 URI는 호출자에 따라 다르다.**
   - 컨테이너 안(backend·auth): `bolt://neo4j:7687` — **같은 compose 네트워크에 있을 때만** 유효(§1-1).
   - 호스트 스크립트(cron·투영 배치): `bolt://127.0.0.1:7687`.
6. **읽기 전용 사용자는 만들 수 없다.** RBAC는 Enterprise 기능이고 이 이미지는 Community라
   실질적으로 `neo4j` 계정 하나다. langgraph-harness §3-3의 "읽기 전용"은 **드라이버 세션 수준
   (`default_access_mode=READ`)에서만** 강제된다 — 그래서 Cypher 화이트리스트는 선택이 아니라
   **DB가 막아주지 못하는 자리를 메우는 의무**다(제약 얘기의 §3 Community 한계와 같은 구조).

---

## 4. 단계별 도입 — 각 단계는 단독 롤백 가능

### 0단계 — 서버만 올린다 (파이썬 코드 0줄)

```bash
# ① 굳은 볼륨 폐기 (516 MB, please_change로 초기화된 것 — 백업 불필요)
docker volume rm comredoceanmap_neo4j_data
docker volume rm redoceanmap_neo4j_data          # 비어 있음, 이름만 정리

# ② 비밀값 등록 — 구 스택 .env · 리포 .env 양쪽 + .env.example 키
#    NEO4J_PASSWORD=<강한 값>   (구 스택 .env의 NEO4J_AUTH 줄은 삭제)

# ③ 서비스 정의(§2)를 구 스택 compose에 추가 후 기동
cd /home/host/projects/redoceanmap
docker compose --profile graph up -d neo4j
docker compose ps neo4j
```

**완료 판정(4개 다 통과해야 1단계로 간다)**

- [ ] `cypher-shell`에서 `CALL dbms.components()` — 버전·edition 확인, 응답 정상
- [ ] 백엔드 컨테이너에서 드라이버 스모크 통과 → **드라이버 6.2.0 ↔ 서버 5.26 조합 최초 검증**
      (neo4j-harness §8의 미해결 항목이 여기서 닫힌다)
- [ ] `docker stats neo4j` 실측이 `mem_limit` 안에 있고, **EXAONE 추론 지연이 변하지 않음**
      (그래프 기동 전/후로 ROM 2.0 질문 하나를 같은 조건에서 재실행해 비교)
- [ ] 헬스체크가 `healthy`로 안정화(§2 각주 — 통과하는 방식 하나만 남기기)

### 1단계 — 스키마와 투영 (neo4j-harness §5-5 게이트를 여기서 채운다)

- 제약·인덱스 `.cypher` 파일(라벨별 `external_id` 유니크) — 적재 스크립트가 `IF NOT EXISTS`로 멱등 적용
- `scripts/project_graph.py` — PG → 그래프 **단방향** 투영, `MERGE` 멱등, 야간 배치
- 대상 라벨은 langgraph-harness §3-2 표(`Area`·`Region`·`Industry`·`Article`·`Topic`)로 한정

**완료 판정:** 스크립트를 연속 2회 돌려 노드·관계 수가 동일(멱등 회귀) · `SHOW CONSTRAINTS` 일치.

### 2단계 — 상시 기동 승격 여부 판단

`reasoning` 분기 로그에서 **멀티홉(3홉 이상) 수요가 실제로 관측된 뒤에만** `profiles`를 떼고
상시 기동으로 올린다(langgraph-harness §5-2 1항). 그때 ROADMAP ①-M2의 "prod neo4j 제외"도
함께 재검토한다 — **지금은 제외 유지**다.

---

## 5. 롤백·폐기

```bash
cd /home/host/projects/redoceanmap
docker compose --profile graph down          # 컨테이너 제거 (backend·auth 무영향 — depends_on 없음)
docker volume rm redoceanmap_neo4j_data      # 데이터 폐기
# compose에서 neo4j 블록 + volumes 한 줄 삭제, .env의 NEO4J_* 삭제
```

**손실 0이다.** 정본은 PG이고 그래프는 재투영으로 복원된다 — 이 성질 때문에
백업 크론도, 오프사이트도 만들지 않는다(pg_dump 크론과 대칭적으로 다루지 않는다).

## 6. 검증 명령 (스택 사실을 반영한 교정판)

```bash
cd /home/host/projects/redoceanmap        # ★ 리포가 아니라 구 스택에서 실행

docker compose --profile graph up -d neo4j
docker compose ps neo4j

# 버전·edition (자격증명은 .env의 NEO4J_PASSWORD)
docker compose exec neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" \
  "CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition;"

# 드라이버 스모크 — 같은 네트워크에서만 이름이 풀린다(§0 함정 ①)
docker exec redoceanmap-backend-1 python -c \
  "from neo4j import GraphDatabase; d=GraphDatabase.driver('bolt://neo4j:7687', auth=('neo4j','$NEO4J_PASSWORD')); d.verify_connectivity(); print('ok')"

# 자원 점유 — 상한 안인지, 추론과 싸우지 않는지
docker stats --no-stream neo4j
free -h

# 포트가 루프백인지 (0.0.0.0 노출 회귀 방지)
docker compose port neo4j 7687          # 127.0.0.1:7687 이어야 한다
ss -ltnp | grep -E "7474|7687"

# 경계 — 접속 코드가 허브 밖으로 샜는지 (게이트 통과 전에는 전부 0줄)
grep -rn --include="*.py" "GraphDatabase" minseok/apps | grep -v "apps/hub/"
```

## 7. 하지 않는다

| 항목 | 사유 |
|---|---|
| 리포 스택에서 neo4j만 띄우고 네트워크로 잇기 | 컨테이너 재생성 시 유실(§1-1). 정의는 백엔드가 사는 스택에 둔다 |
| `depends_on`으로 backend↔neo4j 연결 | 장애 격리 위반. 그래프 부재는 기능 열화지 서비스 중단이 아니다 |
| 메모리 자동 산정에 맡기기 | 기본 힙 ≈ RAM 1/4. EXAONE 7.8B와 같은 10 GiB를 나눠 쓴다(§0) |
| APOC·GDS 플러그인, Enterprise 전환 | Community 전제(neo4j-harness §7). 존재 제약·RBAC가 필요하면 PG로 푼다 |
| `neo4j-admin database dump` 백업 크론 | 파생본이라 복구 대상이 아니다. Community는 온라인 백업도 없다 — 재투영이 복구 절차다 |
| 0.0.0.0 바인딩 / 브라우저 콘솔 외부 노출 | 루프백 유지(neo4j-harness §5-3). 필요하면 SSH 포트포워딩 |
| prod 상시 기동 | ①-M2 제외 유지. 2단계 판정 전까지 `profiles`로 선택 기동 |

## 8. 미해결

- **헬스체크 방식 미확정** — cypher-shell 방식은 컨테이너 안에 비밀번호 주입이 한 번 더 필요하다.
  첫 기동에서 통과하는 쪽으로 하나만 남긴다(§2 각주).
- **드라이버 6.2.0 ↔ 서버 5.26 실연결 미검증** — 0단계 완료 판정 2번이 이걸 닫는 유일한 지점이다.
  실패하면 서버를 올리는 대신 **드라이버를 내리는** 선택지도 있다(`neo4j-graphrag` 제약은 `>=5.17,<7`).
- **`neo4j-graphrag`가 이미지에 안 구워져 있다** — 실행 중 백엔드 컨테이너에 수동 설치만 된 상태라
  컨테이너 재생성 시 사라진다. 그래프 코드를 쓰기 전에 requirements 반영 + 이미지 재빌드가 선행이다.
- **구 스택 compose는 git 밖이다** — 이 문서의 §2 블록이 사실상 그 파일의 유일한 버전 기록이다.
  구 스택 compose를 고칠 때는 이 문서도 같이 고친다.
