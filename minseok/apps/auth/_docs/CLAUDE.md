# CLAUDE.md — auth 앱

백엔드 → [[minseok/_docs/CLAUDE|minseok CLAUDE]]

JWT 기반 인증 스포크. 회원 가입·로그인·토큰 발급을 담당한다.

---

## 역할

- 사용자 계정(`users` 테이블) 영속·조회.
- 비밀번호 해시 검증 + JWT 액세스 토큰 발급(`JWT_SECRET` 환경변수).
- 다른 스포크가 인증이 필요하면 **허브를 경유**한다 — auth를 직접 import하지 않는다(스포크 독립).
- **등급(RBAC 확장, alembic `c3d4e5f6a7b8`)**: `role_tabs`(역할별 노출 탭) 소유. 가입(일반·소셜
  즉시가입·동의 완료) 시 기본 등급 `basic` 자동 부여(`GradeRepository.grant_basic`, 멱등·basic
  부재 시 no-op). 공개 `GET /auth/tabs` — 토큰 유효 시 보유 역할 탭 합집합, 없음/무효 시 basic
  구성 반환. 등급 CRUD는 허브 `GradePolicyPort`를 `GradePolicyGateway`로 구현(어드민 소비).

- **모바일 카카오 로그인(alembic `c9d0e1f2a3b4`)**: `POST /auth/mobile/kakao` — 앱이 보낸 카카오
  액세스 토큰을 서버가 카카오에 직접 확인(`access_token_info`로 **app_id 검증** → `/v2/user/me`)한 뒤
  자체 JWT(`platform=mobile`)를 발급한다. 식별자는 `users.kakao_id`(이메일 연동 아님 — 이메일은
  선택 동의라 NULL 가능). 리프레시는 **Redis db 1**(`mobile:refresh:{user_id}:{jti}`)에 저장하고
  웹 세션(db 0)과 커넥션을 분리한다.
- **모바일 세션 갱신**: `POST /auth/mobile/refresh` — 리프레시를 본문으로 받고 본문으로 돌려준다
  (쿠키 없음). **회전**(쓴 `jti` 즉시 폐기 + 새 쌍 발급, `deviceId`는 저장값 승계)과
  **재사용 탐지**(`mobile:denylist:{jti}` 적중 시 그 유저의 **모바일 세션만** 전량 폐기, 웹은 유지).
  로그아웃 엔드포인트는 아직 없다 →
  [[minseok/_docs/flutter-kakao-oauth-harness|flutter kakao oauth harness]] 8.4·8.5.
- **모바일 동의 가입**: `POST /auth/mobile/consent` — 카카오싱크(비즈니스 앱) 미전환이라
  `service_terms`가 막히는 동안, 필수 약관을 **앱 자체 동의 화면**에서 받는 경로.
  `/kakao`가 신규+동의 미확인이면 403이 아니라 **200 + `consentToken`**(RS256 JWT,
  `purpose="mobile_consent"`, 10분)을 내리고, 앱이 동의를 받아 이 경로로 가입을 마친다.
  `kakao_id`는 요청으로 받지 않는다 — 토큰 서명 안에만 있다 → 같은 문서 8.6.

## 헥사고날 레이어

```
apps/auth/
├── domain/entities/          # User 엔티티 (프레임워크 무의존)
├── app/
│   ├── ports/input/          # AuthUseCase (ABC)
│   ├── ports/output/         # UserRepository (ABC)
│   └── use_cases/            # AuthInteractor
├── adapter/
│   ├── inbound/api/v1/       # auth_router (/auth/*)
│   └── outbound/
│       ├── orm/user_orm.py   # users 테이블 (SQLAlchemy 2.0)
│       └── pg/               # UserPgRepository
└── dependencies/             # DI 프로바이더 (2-function 패턴)
```

**의존 방향:** `adapter → app → domain`. 상세 컨벤션 → [[minseok/_docs/CLAUDE|minseok CLAUDE]].
