# CLAUDE.md — recommendation 앱

백엔드 → [[minseok/_docs/CLAUDE|minseok CLAUDE]]

상권 추천 결과를 기록·조회하는 스포크. chat이 만든 추천을 영속화하고 지도/어드민에서 재조회한다.

---

## 역할

- 추천 1건(`recommendations` 테이블) = 대화·상권·업종·사유·좌표.
- `RecommendationInteractor`(대장)가 저장/조회 유스케이스를 조립한다.
- **기록 경로**: chat → 허브 `RecommendationRecordPort` → recommendation. 스포크끼리 직접 잇지 않는다
  (교차 협력은 허브 경유 — hub CLAUDE 참고). 구현은 `RecommendationRecordGateway`가
  허브 계약 DTO를 도메인 초안으로 변환해 유스케이스에 위임하고, `main.py`가 주입한다.

## 북마크 (③-M2, 2026-08-21)

관심 종목·상권 저장(`bookmarks` 테이블, 루트 체인 `h7a8b9c0d1e2`). "추천 기록"과 "찜"은
동일한 사용자↔분석대상 연결이라 이 스포크가 소유한다(ROADMAP 판정 — CRUD 2~3개짜리
새 스포크는 과설계).

- **API**: `GET /bookmarks/myself`(자기소개) · `POST /bookmarks`(등록) · `GET /bookmarks`
  (내 목록, 최신순) · `DELETE /bookmarks/{target_type}/{target_key}`. 사용자는
  `get_current_user_id`(쿠키/Bearer)로 식별 — 남의 북마크는 경로가 없다.
- **멱등 규칙**: 같은 대상 재등록은 오류가 아니라 기존 행 반환(토글 UI의 재클릭),
  없는 것 삭제는 200(deleted=false). (user_id, target_type, target_key) 유니크.
- **정규화**: 종목 키는 대문자(aapl↔AAPL 혼입 방지 — 인터랙터 소유 규칙, 삭제도 동일 적용).
  label은 저장 시점 표시명 동결(재등록으로 덮지 않는다). 사용자당 상한 200(초과 409).
- **프론트**: `/bookmarks` 페이지(내 목록·삭제) + 주식 히어로·상권 오버레이의
  `BookmarkButton`(서버 목록이 단일 진실 — 로컬 상태 없음, 비로그인 클릭은 로그인 모달).
  game의 `useFavorites`(localStorage 관심종목)와는 별개다 — 그쪽은 시즌 화면 취향.

## 관심 보드 (개인화 ①, ③-M7, 2026-08-23)

`GET /bookmarks/board`(+`/myself`) — 북마크를 "재개 지점"에서 **"내 관심 대상의 지금"**으로
승격한다. 새 수집·새 모델·새 테이블 없음 — 조합만 한다(ROADMAP M7 판정).

- **종목**: 허브 `StockStatusPort`(stock `StockStatusGateway` 구현 — 동결 스냅샷+최근 종가
  2봉, 10일 초과 스냅샷 제외, 접미 변형 흡수)로 방향·전일 대비·검증 참고 여부·기준일.
- **상권**: 기존 허브 `CommercialDataPort.get_area_scores`로 종합점수·등급 + 전분기 대비
  (매출 성장 컴포넌트의 QoQ — 라우터가 추출).
- **격리가 게이트다**: 조회 범위가 처음부터 `find_by_user(user_id)`뿐이라 남의 상태가 섞일
  경로가 없다 — `test_bookmark_board_interactor.py`가 격리·열화·정렬을 고정.
- **열화**: 상태 조회 실패·스냅샷 없는 종목·점수 없는 상권은 상태 없이 나간다(목록은 항상
  뜬다). 정렬은 **등록 최신순 고정**(M8 실사용자 게이트 전까지).
- **프론트**: `/bookmarks` 페이지가 보드를 렌더 — 방향 뱃지·등락률·종합점수, 상태 없으면
  "상태 준비 중" 문구. ⛔ 홈에는 넣지 않는다(2026-08-16 리뉴얼 결정 유지).

## 투자·창업 프로파일 (개인화 ⓪, 2026-08-22)

자기신고 설문(`user_profiles` 테이블, 루트 체인 `i8b9c0d1e2f3`) — 사용자당 1행.
북마크와 같은 "사용자↔분석대상" 축의 심화라 이 스포크가 소유한다(ROADMAP 판정 —
개인화는 recommendation 확장). **마이데이터 연동·신용점수 조회는 하지 않는다**
(본인신용정보관리업 허가·유료 API 필요). 정확한 금액 대신 **밴드(구간)만** 받는다.

- **API**: `GET /profile/myself`(자기소개) · `GET /profile`(내 것 — 미작성이면
  `profile=null`, 404 아님) · `PUT /profile`(저장/재작성 — 덮어쓰기) · `DELETE /profile`
  (멱등 — 없는 것 삭제는 200 deleted=false).
- **어휘**: purpose(startup|invest|both) · risk_level(1~5, 증권사 투자성향 5등급) ·
  budget_band(under_30m~over_300m) · debt_burden(none|manageable|heavy) ·
  horizon(short|mid|long). **라벨 문장의 단일 정의처는 `profile_entity.py`** —
  화면·프롬프트 라벨이 여기서 갈라지지 않는다.
- **소비 경로**: chat → 허브 `UserProfilePort` → 이 스포크 `UserProfileGateway`.
  chat이 phase2(상권)·주식 서술 컨텍스트에 라벨을 주입한다 — **서술 관점 조정까지만**,
  프로파일을 근거로 한 매매 권유·예산 적합 단정은 프롬프트 규칙으로 금지(투자자문 경계).
- **프론트**: `/profile` 설문 페이지(FormData 패턴, 라디오 밴드 선택·삭제 버튼).

## 레이어

```
apps/recommendation/
├── domain/entities/recommendation_entity.py   # Recommendation (frozen)
├── app/
│   ├── dtos/recommendation_dto.py              # RecommendationDraft
│   ├── ports/input/recommendation_use_case.py
│   ├── ports/output/recommendation_repository.py
│   └── use_cases/recommendation_interactor.py  # 대장
├── adapter/
│   ├── inbound/api/v1/recommendation_router.py # GET /recommendations[/conversation/{id}]
│   └── outbound/
│       ├── orm/recommendation_orm.py           # recommendations 테이블
│       ├── mappers/recommendation_mapper.py
│       ├── pg/recommendation_pg_repository.py
│       └── gateways/recommendation_record_gateway.py  # 허브 RecommendationRecordPort 구현
└── dependencies/recommendation_provider.py     # 유스케이스 + 기록 게이트웨이 프로바이더
```

**의존 방향:** `adapter → app → domain`. 컨벤션 → [[minseok/_docs/CLAUDE|minseok CLAUDE]].
