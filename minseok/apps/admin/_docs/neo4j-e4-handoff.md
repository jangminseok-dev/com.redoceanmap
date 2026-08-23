# NEO4J ①-E4 인수인계 로그 — 백엔드 PC 작업용 (2026-08-23)

작성: 맥(mac 브랜치) 세션. 다음 작업은 **백엔드 PC(window 브랜치)에서 진행**한다 —
수요 계수에 필요한 `langchain_turns` 실데이터·구 스택이 그쪽에만 있다.

운영 규칙 → [[minseok/apps/admin/_docs/neo4j-harness|neo4j-harness]] ·
설치·기동 → [[minseok/apps/admin/_docs/neo4j-strategy|neo4j-strategy]] ·
계수 방법 → [[minseok/apps/admin/_docs/langgraph-strategy|langgraph-strategy]] §4-1 ·
로드맵 → [[minseok/_docs/ROADMAP|ROADMAP]] ①-E4

---

## 1. 현재 상태 (2026-08-23 리포 실측)

| 단계 | 상태 |
|---|---|
| 0단계 — 서버 기동 (구 스택 `neo4j:5.26`, 루프백, 비밀번호 교체) | ✅ 2026-07-30 |
| 1단계 — 제약 5종 + PG→그래프 투영 (노드 3,582 / 관계 79,188) + cron 02:15 | ✅ 2026-07-30 |
| **게이트(neo4j-harness §5-5)** | ⚠️ 4개 중 2개 미충족 — 아래 §2 |
| 런타임 질의 코드 | **0건** (`hub/adapter/outbound/graph/` 자리만 예약 — 게이트 통과 전 코드 금지) |
| 2단계 — 상시 기동 승격·prod 편입 | 보류 (멀티홉 수요 관측 후) |

## 2. 남은 게이트 2개

1. **그래프로만 답하는 질문의 실수요 미확인** — 4홉 질의 실동작은 확인됐지만
   *사용자가 실제로 그런 질문을 하는가*가 비어 있다. → 아래 §3-1이 첫 작업.
2. **장애 격리 코드 없음** — 설계는 langgraph-harness §2-3(`degraded` + rag 폴백)에 있고,
   런타임 질의 경로를 만드는 커밋에서 함께 구현한다.

## 3. 작업 순서 (백엔드 PC)

### 3-1. 게이트 답안: 질문 10개 명세서 (코드 0줄)

실 DB에서 질문을 뽑아 **10개를 문서로 적고** `vector-ok` / `pg-join` / `graph-only` 판정
라벨을 붙인다(langgraph-strategy §4-1 — 추측으로 만들지 않는다).

```sql
-- redoceanmap-pgvector-1 (공유 DB)에서. content가 질문 컬럼, role='user' 필수
SELECT t.content AS question, t.created_at
FROM langchain_turns t
WHERE t.role = 'user' AND t.destination = 'rag'
ORDER BY t.created_at DESC LIMIT 200;
```

**착수 조건: `graph-only`(3홉 이상)가 10개 중 3개 이상.** 미만이면 3단계 보류가
문서상 올바른 결론이다 — 게이트 면제 없음. GraphRAG(chat 근거 확장)가 유일한
그래프 우위 후보라는 실사는 ROADMAP ①-E4에 이미 있다.

### 3-2. 게이트 통과 시 — 허브 접속 코드 첫 커밋

- 위치는 `hub/adapter/outbound/graph/`만. 스포크(chat·admin)는 Bolt 직접 접속 금지,
  허브 포트 소비. 수직 슬라이스 1:1(포트+DTO+게이트웨이+스텁 테스트).
- 접속 정보는 `core/config.py` 상수 경유(`NEO4J_*`는 `.env.example` 등록 완료).
- **장애 격리(§2-2)를 같은 커밋에** — 그래프 조회 실패는 500이 아니라 섹션 부재/`degraded`.
- 신규 라벨이 필요하면 라벨·속성 표를 neo4j-harness에 먼저 적고 제약 Cypher를 같은 커밋에.

### 3-3. 검증

```bash
# 경계 — 게이트 통과 전 0줄, 통과 후에도 hub 밖 0줄
grep -rn --include="*.py" "GraphDatabase\|neo4j_graphrag" minseok/apps | grep -v "apps/hub/"
cd minseok && PYTHONPATH=apps lint-imports
# 실연결 스모크·자원·루프백 → neo4j-strategy §6 (구 스택에서 실행)
```

## 4. 하지 않는다 (기존 문서 고정 사항)

GDS·Enterprise 기능 · PG 전면 이관 · 그래프 백업 크론(재투영이 복구 절차) ·
그래프 전용 어드민 페이지 · `depends_on` 연결 · prod 상시 기동(2단계 판정 전).

## 5. 완료 후

- 이 파일에 결과(판정 표·착수/보류 결론)를 덧붙이거나, 명세서를 langgraph-strategy §4-1
  산출물로 정식 편입하고 이 로그는 삭제한다.
- ROADMAP ①-E4 행 갱신 + 세 브랜치(`window`·`mac`·`main`) 동기화.
