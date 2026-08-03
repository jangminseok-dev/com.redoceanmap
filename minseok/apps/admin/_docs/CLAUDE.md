# CLAUDE.md — admin 앱

백엔드 → [[minseok/_docs/CLAUDE|minseok CLAUDE]]

운영 콘솔(어드민) 스포크. 회원·상권·추천·데이터셋 현황을 열람하고 역할(RBAC)을 부여/회수한다.
도메인 데이터는 허브 포트를 경유해 소유 스포크(auth·market·recommendation·stock)에서 오고,
**자체 ORM은 둘**(`admin_audit_logs` · `admin_pdf_documents`) — 어드민 자신의 행위 기록과
어드민이 업로드한 운영 문서라 허브 경유 없이 직접 영속한다.

---

## 역할

- `/admin/*` 엔드포인트 표면 소유. 인증(JWT)은 main.py 공통, 권한은 엔드포인트 단
  `require_permission("<code>")`(core/security — 매 요청 DB 조회라 역할 회수 즉시 반영).
- 프론트 `/admin` 가드 판정: `GET /admin/me` — 호출자의 permission 코드 목록(빈 배열 = 비관리자).
- 권한 코드 10종: `dashboard:read` · `areas:read` · `members:read` · `members:write` ·
  `recommendations:read` · `datasources:read` · `audit:read` · `analytics:read` ·
  `documents:read` · `documents:write`. RBAC 테이블(roles 등 4종)은 **auth 소유**,
  시드는 alembic `f0a1b2c3d4e5`(6종) + `a1b2c3d4e5f6`(audit:read) + `c1d2e3f4a5b6`(analytics:read)
  + `c6d7e8f9a0b1`(documents:read/write), 최초 부여는 `scripts/grant_admin.py <email>`.
- **감사 로그**: 역할 부여/회수·정지/해제/세션 폐기/탈퇴 등 변경 행위를 `AuditLogPort`(PG,
  `admin_audit_logs`)에 기록한다. steward record 포트(로그 출력, 관찰성)와 구분 —
  매 요청성 관찰은 DB에 남기지 않는다.
- **회원 제재**(alembic `b2c3d4e5f6a7` — users.suspended_at/suspended_reason/deleted_at):
  정지는 즉시 차단(core/security.get_current_user_id가 매 요청 users 상태 검사, 기발급
  액세스 토큰도 403) + 리프레시 토큰 전량 폐기(강제 로그아웃). 해제는 상태만 복원 —
  세션은 복원하지 않고 재로그인(표준). 탈퇴는 비가역 — 개인정보 익명화
  (email=deleted-{id}-{rand}@removed.local, name=탈퇴회원, 비번 무효화) + 역할 회수 + 토큰 폐기.
  약관 제8조의 이메일 접수 탈퇴 요청을 운영자가 처리하는 도구다.
  - **배포 순서 주의**: get_current_user_id가 매 요청 `suspended_at/deleted_at`을 SELECT하므로,
    신코드 재기동 **전에 반드시 alembic upgrade**를 먼저 해야 한다(컬럼 부재 시 전 인증 요청 500).
  - 세션 강제 폐기는 Redis 역인덱스 우선 + `SCAN` 폴백이라 역인덱스 도입 전 발급된 레거시
    토큰도 누락 없이 폐기한다(관리 작업 저빈도라 SCAN 비용 무시).

## 슬라이스 (1:1 컨벤션)

| 슬라이스 | 엔드포인트 | 소비 허브 포트 |
|---|---|---|
| steward (페르소나) | GET /admin/myself · GET /admin/me | MemberDirectoryPort |
| dashboard | GET /admin/dashboard | MemberDirectory + RecommendationDirectory + CommercialData + **StockDemand**(top_demands 30일·10건 — 워치리스트 자동 편입 후보를 운영자도 본다) |
| member | GET /admin/members · GET /admin/members/roles · POST/DELETE /admin/members/{id}/roles[/{code}] · POST /admin/members/{id}/{suspend,reinstate,revoke-sessions,withdraw} | MemberDirectoryPort |
| grade | GET/POST /admin/grades · PATCH/DELETE /admin/grades/{code} — 등급(=역할)별 탭 노출 구성. 권한은 members:read/write 재사용, 탭 키는 허브 tab_ontology 검증, admin은 삭제·개명 차단(탭 변경 허용), 감사 grade.create/update/delete | GradePolicyPort |
| area | GET /admin/areas | CommercialDataPort (get_area_overview) |
| recommendation_log | GET /admin/recommendations | RecommendationDirectoryPort |
| data_source | GET /admin/data-sources | CommercialData (get_dataset_stats) + RecommendationDirectory + **StockDatasetStats** (get_dataset_stats) — 상권 5 + 추천 + 주식 5 = 11장. 각 카드에 순수 도메인 `dataset_freshness.evaluate`로 신선도(정상/지연/정지/불명/정적) 판정을 붙인다 |
| audit | GET /admin/audit | 자체 AuditLogPort (member 슬라이스가 write, audit 슬라이스가 열람) |
| pdf_loader | POST /admin/pdf-documents(업로드·요약, documents:write) · GET /admin/pdf-documents[/{id}](documents:read) — PDF 텍스트 추출(neo4j-graphrag `PdfLoader`) → EXAONE 요약 → `admin_pdf_documents` 저장, 감사 `pdf.summarize`. 원본 PDF는 미보관(임시파일 즉시 삭제), 요약 입력은 앞 6000자 단발 | 자체 PdfDocumentRepository + PdfTextExtractorPort + PdfSummarizerPort + AuditLogPort |
| image_upload | POST /admin/images(멀티파트 업로드, documents:write) — 바이트 매직 넘버로 형식 판정(jpeg/png/webp/gif, 10MB) → `admin/images/YYYY/MM/<uuid>.<ext>` 키로 S3 저장 → 사전서명 조회 URL(15분) 반환, 감사 `image.upload`. DB 영속 없음(객체 + 감사 기록만), 원본 파일명은 키에 쓰지 않는다. 버킷 env `ADMIN_IMAGE_S3_BUCKET` 미설정 시 이 엔드포인트만 503 | 자체 ImageStoragePort(S3) + AuditLogPort |
| analytics | GET /admin/forecasts · GET /admin/market-backtest · GET /admin/news-event-study — 예측 스냅샷 채점 현황(적중률·신호별 일치율·최근 목록) + 상권 점수 백테스트 최신 리포트. 권한 analytics:read 공용 | ForecastSnapshotPort (accuracy_report) + AreaBacktestReportPort (latest) + NewsEventStudyPort (latest) |

인터랙터는 허브 포트를 생성자 주입받고, 프로바이더는 허브 스텁 프로바이더를 `Depends`로 받는다
(합성 루트 main.py의 `dependency_overrides`가 스포크 게이트웨이로 치환 — 계약 상세는 hub CLAUDE).

## 레이어

```
apps/admin/
├── domain/services/dataset_freshness.py         # 수집 신선도 판정(순수) — 기대 주기 표 + evaluate
├── domain/services/image_upload_policy.py       # 이미지 허용 형식·크기·객체 키 규칙(순수) — inspect/build_object_key
├── app/
│   ├── dtos/{steward,dashboard,member,area,recommendation_log,data_source,audit}_dto.py
│   ├── ports/input/{...}_use_case.py            # 슬라이스별 UseCase ABC
│   ├── ports/output/steward_record_port.py      # steward 활동 기록(로그 출력)
│   ├── ports/output/audit_log_port.py           # 감사 로그(PG 영속 — 변경 행위만)
│   ├── ports/output/pdf_{text_extractor,summarizer}_port.py  # PDF 추출 · LLM 요약
│   ├── ports/output/pdf_document_repository.py  # 요약 문서 영속
│   ├── ports/output/image_storage_port.py       # 이미지 객체 저장(구현은 S3 — 계약은 스토리지 중립)
│   └── use_cases/{...}_interactor.py
├── adapter/
│   ├── inbound/api/{schemas,v1}/{...}_{schema,router}.py
│   └── outbound/
│       ├── log_steward_record_adapter.py        # 임시 로그 구현
│       ├── pdf_loader_extractor_adapter.py      # neo4j-graphrag PdfLoader (to_thread)
│       ├── exaone_pdf_summarizer_adapter.py     # LLM 오케스트레이터 경유 요약
│       ├── s3_image_storage_adapter.py          # boto3 put_object + 사전서명 URL (to_thread, 클라이언트 지연 생성)
│       ├── orm/{audit_log,pdf_document}_orm.py  # admin_audit_logs · admin_pdf_documents
│       └── pg/{audit_log,pdf_document}_pg_adapter.py
├── dependencies/{...}_provider.py
└── tests/app/use_cases/test_{...}_interactor.py # 스텁 허브 포트로 검증
```

**의존 방향:** `adapter → app → domain`. 컨벤션 → [[minseok/_docs/CLAUDE|minseok CLAUDE]].
