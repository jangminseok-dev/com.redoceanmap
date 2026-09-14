# CLAUDE.md — 프론트엔드 (www)

루트 → [[CLAUDE|CLAUDE (루트)]]

Next.js 프론트엔드. UI 원자(버튼·모달·입력)는 **shadcn/ui**로 만든다(2026-08-04 도입).

## 공개 페이지 — 서버 컴포넌트 (2026-09-14, A-4)

`app/areas/[trdarCode]/page.tsx`·`app/sitemap.ts`·`app/robots.ts`는 이 저장소의 **첫 서버 컴포넌트
경로**다. `(seoul)` 그룹 밖이라 TabGuard가 걸리지 않고, 백엔드 **공개** 엔드포인트만 읽는다.
서버 fetch는 `lib/publicApi.server.ts` 하나로 모은다 — "브라우저 fetch 절대 URL 금지"의 서버 측 예외이며,
클라이언트 컴포넌트에서 import하면 안 된다(그쪽은 `lib/api.ts`). ISR은 하루(분기 데이터).

## 개발 서버 — `--webpack`을 떼지 말 것

```bash
cd www && pnpm run dev     # = next dev --webpack
```

**Turbopack(Next 16 기본)으로 돌리면 브라우저가 접속하는 순간 `next dev`가 CPU를 점유해
기기가 멎는다.** 2026-08-04 실측: `node` 141.8% + 워커 프로세스 10개 + 931MB, `kernel_task`가
96.3%까지 올라가 발열 스로틀링에 들어갔다. 재부팅 외에 복구가 안 된다.

- 원인은 백엔드·프록시가 아니다 — 8000·9000 정상(401·200), `fseventsd` 1.3%로 낮고,
  브라우저 프로세스는 조용하다. 번들러만 바꾸면 사라진다
- `curl`로는 재현되지 않는다. HMR 웹소켓이 붙어야 시작되므로 페이지 HTML·JS 청크를
  전부 받아도 조용하다(직후 60~70% 스파이크 후 유휴 0%). **브라우저로만 재현된다**
- `next build`는 Turbopack이어도 멀쩡하다(watch가 없다). 배포는 영향 없다

`.next`는 `build`와 `dev` 산출물이 한 디렉토리에 섞인다. 번갈아 쓴 뒤 dev가 이상하면
`rm -rf .next` 후 재기동한다.

---

## 자동 적용 규칙

작업 영역에 해당하면 사용자 지시 없이 아래 규칙을 먼저 읽고 적용한다.

| 문서 | 적용 시점 |
| --- | --- |
| [[www/_docs/DESIGN\|DESIGN]] | 화면을 만들거나 고칠 때 — 색·크기·간격·모션의 정본. 여기 없는 값을 새로 만들지 않는다 |
| [[www/_docs/REACT_RULES\|REACT_RULES]] | `.tsx` / `.ts` / `.jsx` / `.js`를 작성·수정할 때 — 한 컴포넌트에 `useState`가 2개 이상이면 FormData 패턴 또는 단일 객체 패턴으로 자동 압축 |
| 아래 "shadcn 규칙" | 버튼·모달·입력·탭 등 **UI 원자**를 새로 만들 때 |

> `DESIGN.md`의 실체는 `www/_docs/DESIGN.md`이고, `www/DESIGN.md`와 저장소 루트 `DESIGN.md`가
> 심볼릭 링크로 가리킨다. 루트 링크는 편집을 감시하는 `post-edit-watch` 훅이
> `$CLAUDE_PROJECT_DIR/DESIGN.md`만 읽기 때문에 필요하다 — 지우면 훅이 대조를 못 한다.

규칙에 해당하면 자동으로 적용하고, 어떤 패턴을 적용했는지 한 줄로 명시한다.
(사용자가 "useState 유지"처럼 명시적으로 요청한 경우 제외)

---

## shadcn 규칙 (필수)

### 1. UI 원자를 직접 만들지 않는다

`<button>` · `<input>` · `<textarea>` · 모달 오버레이를 새로 손으로 짜지 않는다.
`components/ui/`의 컴포넌트를 쓴다.

| 만들 것 | 쓸 것 | 직접 짜면 생기는 문제 |
| --- | --- | --- |
| 버튼 | `Button` | focus ring·`disabled` 처리를 매번 다시 씀 |
| 모달·확인창 | `Dialog` | 포커스 트랩·스크롤 락·Escape를 직접 구현하게 됨 |
| 텍스트 입력 | `Input` / `Textarea` | `aria-invalid`·focus 스타일이 화면마다 갈림 |
| 라벨 | `Label` | `htmlFor` 연결 누락 |
| 탭 | `Tabs` | 키보드 내비·`aria-selected` 누락 |
| 드롭다운 | `DropdownMenu` | hover 전용이 되어 모바일에서 열 수 없음 |

현재 설치된 것: `button` · `dialog` · `input` · `textarea` · `label` · `tabs` · `dropdown-menu`.

### 2. 없는 컴포넌트는 CLI로 가져온다

```bash
cd www && pnpm dlx shadcn@latest add <name>   # 예: select, checkbox, table
```

- `components/ui/`에 파일이 생기면 **그 파일은 우리 코드다** — 필요하면 고쳐 쓴다.
- `init`은 다시 돌리지 않는다. `app/globals.css`를 덮어써 기존 토큰이 날아간다.
- 애니메이션 유틸(`animate-in`·`zoom-in-95`)은 `tw-animate-css`가 제공한다.
  Tailwind 4에 내장돼 있지 않으므로 이 import를 지우면 모달 애니메이션이 죽는다.

### 3. 색은 기존 토큰이 정본이다

shadcn 표준 이름은 **기존 색을 가리키는 별칭**이다(`app/globals.css`).

| shadcn 이름 | 실제 값 |
| --- | --- |
| `--primary` | `var(--brand)` |
| `--card` · `--popover` | `var(--surface)` |
| `--muted-foreground` | `var(--foreground-muted)` |
| `--input` | `var(--border)` |

- **새 색을 만들지 않는다.** 필요하면 위 토큰 중에서 고른다.
- 기존 토큰(`bg-brand`·`bg-surface`·`text-foreground-muted`)은 그대로 쓴다 — 폐기 대상이 아니다.
- 컴포넌트 기본 스타일을 덮을 때는 `className`으로 넘긴다. `cn()`(`@/lib/utils`)의
  twMerge가 뒤에 온 클래스를 이기게 해준다.

### 3-1. 크기는 `size`로 고른다 — 높이·radius·폰트를 따로 주지 않는다

| size | 높이 | radius | 폰트 | 용도 |
| --- | --- | --- | --- | --- |
| `sm` | 32px | 8px | 13px / 500 | 인라인·칩·테이블 액션 |
| `md`(기본) | 40px | 12px | 14px / 500 | 기본 폼·대화상자 |
| `lg` | 48px | 12px | 15px / 600 | 섹션 주요 액션 |
| `xl` | 56px | 16px | 17px / 600 | 화면 단위 주요 액션(주문·가입) |

```tsx
<Button size="xl" className="w-full">가입하기</Button>       {/* 좋음 */}
<Button className="h-11 py-3 rounded-lg text-base">가입</Button>  {/* 나쁨 — 스케일 밖 */}
```

- **표에 없는 높이·radius를 새로 만들지 않는다**(`h-11`·`h-9`처럼). 맞는 단계를 고른다.
- 진행 상태는 `loading` prop을 쓴다 — 라벨 자리를 남겨 **버튼 너비가 유지된다**.
  폭이 이미 `w-full`로 고정된 자리에서는 라벨을 바꿔도 된다(정보가 더 많다).
- 보조 액션은 `variant="weak"`. 손으로 `bg-brand/10 text-brand`를 쓰지 않는다.
- 텍스트 버튼에 `rounded-full`을 쓰지 않는다. 아이콘 버튼·아바타·뱃지에만 쓴다.

### 4. 정리는 끝났다 — 새 코드는 처음부터 스케일로 쓴다

2026-08-04에 토큰·크기 스케일 정리를 한 번에 마쳤다. 이제 **새로 만드는 화면은 처음부터
§3-1 표에서 크기를 고르고 `Button`/`Input`을 쓴다.** 손으로 기하를 쓰지 않는다.

기존 화면을 고칠 때는 여전히 Surgical Changes가 우선이다 — 고치는 부분만 바꾸고
주변까지 훑지 않는다.

아직 네이티브로 남아 있고, 옮기려면 로직을 함께 고쳐야 하는 것들:

| 대상 | 남긴 이유 |
| --- | --- |
| `<select>` | `value`/`onChange` → `onValueChange` + Trigger/Content/Item 구조로 전면 재작성 필요 |
| 체크박스 | 회원가입 "전체 동의"가 `form.elements`를 직접 조작한다 |
| 탭 2곳(워크스페이스·주식) | 패널을 한 번만 마운트하고 CSS로 전환하는 구조 — 지도·차트 이중 인스턴스 방지가 목적이라 `Tabs`로 옮기면 `forceMount`가 필요해진다 |
| 필터 칩·세그먼트 토글 | `Button` 스케일과 섞이면 안 되는 낮은 위계 요소다. 알약(`rounded-full`)을 유지한다 — DESIGN.md §5 |

### 5. 모션은 의존성 없이 만든다

모션 라이브러리를 쓰지 않는다. 지금 필요한 네 가지(모달 진입·리스트 진입·숫자 변화·첫 진입)는
CSS와 `requestAnimationFrame`으로 충분하고, 그 이상은 DESIGN.md §15가 금지한다.

| 필요 | 쓸 것 |
| --- | --- |
| 모달·시트 진입 | `Dialog`가 이미 CSS로 처리(`tw-animate-css`) |
| 요소 진입 | `animate-fade-in-up` |
| 숫자 변화 | `CountUp`(`@/components/common/CountUp`) — **값이 바뀔 때만** 움직인다 |
| 로딩 자리표시 | `.skeleton` |

`framer-motion`이 필요해지는 건 스프링 물리·제스처·레이아웃 애니메이션을 쓸 때다.
그런 요구가 실제로 생기면 그때 넣는다. duration은 §15의 3단(150/200/280ms) 밖으로 나가지 않는다.

### 5. 검증

```bash
cd www && pnpm run typecheck
```

`components/ui/`는 검증에서 빼지 않는다. 시각 회귀를 잡을 테스트 러너가 없으므로,
UI를 바꿨으면 `pnpm run dev`로 **모바일 폭(375px)과 데스크탑을 둘 다** 눈으로 확인한다.
