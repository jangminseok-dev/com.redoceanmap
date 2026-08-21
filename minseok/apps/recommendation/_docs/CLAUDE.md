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
