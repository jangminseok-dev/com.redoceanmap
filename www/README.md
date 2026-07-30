# www — redoceanmap 프론트엔드

Next.js 16 · React 19 · TypeScript 5(strict) · Tailwind 4 · zustand · TanStack Query.

작업 규칙은 문서가 정본이다 — 코드를 고치기 전에 읽는다:
`_docs/CLAUDE.md` · `_docs/REACT_RULES.md` · 저장소 루트 `.claude/rules/typescript.md`.

## 명령어

패키지 매니저는 **pnpm**이다(`pnpm-lock.yaml`이 정본).

```bash
pnpm install          # 최초 1회
pnpm run dev          # 개발 서버 :3000
pnpm run typecheck    # 타입 체크 — 이 프로젝트의 유일한 자동 검증 수단
pnpm run build        # 프로덕션 빌드
```

**`npx tsc --noEmit`을 쓰지 않는다.** 로컬 typescript를 못 찾으면 레지스트리의 무관한 `tsc`
패키지를 설치하고 **exit 0으로 끝나** 타입 체크를 하지 않았는데 통과한 것처럼 보인다
(2026-07-30 실측: 에러 19건이 이렇게 가려져 있었다). 반드시 위 스크립트로 돌린다.

테스트 러너는 없다. 타입 체크가 유일한 그물이므로 `any`를 넣지 않는 것이 중요하다.

## 백엔드 연결

브라우저 fetch는 **절대 URL을 쓰지 않는다** — `next.config.ts`의 `/api/backend` rewrite를
경유한다. 절대 URL로 직접 부르면 쿠키가 실리지 않아 로그인이 깨진다(2026-07-15 실장애).

응답 필드명은 백엔드가 준 그대로 쓴다(snake_case면 snake_case). 변환 계층이 곧 버그 지점이다.

## 배포

`main` 브랜치 push 시 **Vercel이 자동 배포**한다. 로컬에 프론트 컨테이너는 없다.

환경 변수는 `www/.env.local`(로컬)과 Vercel 환경 변수(배포)에 각각 둔다 — Next.js는
`www/` 안의 env 파일만 읽으므로 저장소 루트 `.env`는 프론트에 전달되지 않는다.
키 목록은 루트 `.env.example`의 "Frontend (www/)" 구획을 본다.

## 알아둘 함정

- **쿼리스트링만 바꾸는 내비게이션은 `history.replaceState`를 쓴다.** `router.replace/push`는
  프로덕션 빌드에서 무시된다(개발 서버에서는 재현되지 않아 배포 후에야 드러난다).
- `useSearchParams()`·`usePathname()`은 타입상 `| null`이다. 옵셔널 체이닝으로 받되
  `?? null`로 원래 타입을 유지한다 — 빼면 `| undefined`가 붙어 하위 사용처가 흔들린다.
- `.next/types`에 구 경로 캐시가 남아 오탐하면 `rm -rf .next/types` 후 재실행한다.
