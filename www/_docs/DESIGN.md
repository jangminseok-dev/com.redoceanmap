---
omd: 0.1
brand: redoceanmap
bootstrapped_from: toss
bootstrapped_at: 2026-08-04
tokens:
  source: project-current
  extracted: "2026-08-04"
  note: "레퍼런스(toss)의 기하·상태·문서 구조를 따르되 색은 redoceanmap 현행을 유지한다. canvas/surface 역할이 레퍼런스와 반대다."
  colors:
    primary: "#991B1B"
    primary-hover: "#7A1515"
    canvas: "#FDFAF2"
    foreground: "#1A1A1A"
    muted: "#6B7280"
    surface: "#FFFFFF"
    border: "#EBE8DF"
    on-primary: "#FFFFFF"
    weak-background: "#F0EDE6"
    weak-foreground: "#991B1B"
    secondary: "#F5F1E8"
    danger: "#DC2626"
    up: "#DC2626"
    down: "#2563EB"
    up-weak: "#FEF2F2"
    down-weak: "#EFF6FF"
  typography:
    family: { sans: "Pretendard Variable" }
    data-xl: { size: 28, weight: 700, lineHeight: "1.15" }
    data-l: { size: 20, weight: 600, lineHeight: "1.3" }
    h1: { size: 36, weight: 600, lineHeight: "1.375" }
    h2: { size: 20, weight: 700, lineHeight: "1.4" }
    h3: { size: 16, weight: 600, lineHeight: "1.5" }
    body: { size: 14, weight: 400, lineHeight: "1.5" }
    body-small: { size: 12, weight: 400, lineHeight: "1.5" }
  spacing: { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 }
  rounded: { chip: 6, button-small: 8, button-medium: 12, button-large: 12, button-xlarge: 16, circle: 9999 }
  components:
    button: { type: button, bg: "#991B1B", fg: "#FFFFFF", radius: "16px", height: "56px", padding: "0 20px", font: "17px / 600", states: "fill or weak; primary, danger, outline, ghost; loading, disabled, pressed, and keyboard focus", use: "화면 단위 주요 액션(주문·가입)" }
    button-weak: { type: button, bg: "#F0EDE6", fg: "#991B1B", radius: "12px", height: "40px", padding: "0 16px", font: "14px / 500", states: "loading, disabled, pressed, keyboard focus", use: "섹션 내 보조 액션" }
    text-field: { type: input, states: "focus, error, disabled, read-only", use: "라벨·도움말·오류문구를 동반한 텍스트 입력" }
    badge: { type: badge, states: "semantic color variants; 등급·상태 표시", use: "상태 라벨. 액션이 아니다" }
    agreement: { type: toggle, states: "checked, unchecked, 전체동의 계층", use: "회원가입 약관 동의" }
---

# Design System of redoceanmap

## 1. Visual Theme & Atmosphere

redoceanmap은 서울 상권과 주식이라는 두 개의 무거운 판단 영역을 "물어보면 답이 오는" 형태로 바꾸려는 웹앱이다. 표면은 두 종류로 나뉜다. 홈은 처음 들어온 사람에게 서비스를 설명하는 유일한 자리이고, 나머지(상권·주식 워크스페이스, 게임, 어드민)는 매일 반복해서 쓰는 제품 화면이다. 두 표면은 관련되어 있지만 같지 않다. 이 문서는 둘을 하나의 평균값으로 뭉개지 않고 표면별로 분리해 기록한다.

색은 크림 배경 위의 진한 적색 한 점이다. 이 조합은 금융 서비스의 관습적인 청색 계열과 다르며, 프로젝트 정체성이므로 유지한다. 기하·간격·상태·모션은 레퍼런스의 체계를 따른다.

**Key Characteristics:**
- Primary `#991B1B`, 배경은 흰색이 아닌 크림 `#FDFAF2`
- Pretendard Variable을 전 화면에서 사용
- 버튼은 높이·radius·폰트가 한 세트로 움직이는 4단 스케일
- 마케팅 표면이 없다 — 화면 대부분이 제품 내부다

## 2. Color Palette & Roles

### Product and shared roles
- **Primary** (`#991B1B`): 주요 액션과 브랜드 강조.
- **Primary Hover** (`#7A1515`): primary의 hover 상태.
- **Canvas** (`#FDFAF2`): 기본 배경. 레퍼런스와 달리 흰색이 아닌 크림이다.
- **Surface** (`#FFFFFF`): 카드·패널·모달이 올라가는 면. 레퍼런스에서는 회색 레이어가 맡는 역할을 여기서는 흰색이 맡는다.
- **Foreground** (`#1A1A1A`): 본문 최강 텍스트.
- **Muted** (`#6B7280`): 보조 텍스트.
- **Border** (`#EBE8DF`): 구분선·외곽선.
- **On Primary** (`#FFFFFF`): 채운 primary 위의 텍스트.
- **Weak Background** (`#F0EDE6`) / **Weak Foreground** (`#991B1B`): 보조 액션용 약한 쌍. 코드에 흩어져 있던 `bg-brand/10 text-brand` 패턴이 이 역할이다.
- **Secondary** (`#F5F1E8`): 조용한 중립 레이어.
- **Danger** (`#DC2626`): 파괴적 행위와 오류.

### Direction roles — 값의 방향

상권·주식·게임 화면이 쓰는 **별도의 축**이다. 브랜드 적색과 값이 가깝다고 합치지 않는다 —
브랜드는 "우리 서비스"를, 이 둘은 "수가 어느 쪽으로 움직였나"를 말한다.

- **Up** (`#DC2626`) / **Down** (`#2563EB`): 한국 시장 관례(상승 빨강 · 하락 파랑). 국제 관례와 반대이며 의도된 것이다.
- **Up Weak** (`#FEF2F2`) / **Down Weak** (`#EFF6FF`): **등락률 배경 하이라이트**. 값이 아니라 값의 세기가 먼저 읽히게 하는 장치다(레퍼런스 토스증권 테이블의 시그니처).

`text-red-600`·`text-blue-600`처럼 Tailwind 기본 팔레트를 직접 쓰지 않는다. `text-up`·`bg-up-weak` 토큰을 쓴다.
차트 라이브러리처럼 CSS 변수를 못 받는 경계에서만 `#DC2626` 리터럴을 쓰고, 파일 상단 상수로 올린다
(`components/stock/CandleChart.tsx`·`components/market/overlay/DemandSection.tsx`가 그 예다).

**등급처럼 단계가 3개를 넘어도 새 색을 만들지 않는다.** 방향은 텍스트(`text-up`/`text-down`)가 말하고
강약은 배경 농도(`bg-up-weak` ↔ `bg-up-weak/50`)가 맡는다. 5단계 상권 등급이 이 방식이다
(`components/market/AreaScoreCard.tsx`) — 단계 이름이 라벨로 적혀 있으므로 색이 혼자 5단계를 구분할 필요는 없다.

### Marketing-web roles
이 프로젝트에는 마케팅 전용 표면이 없다. 홈(`app/(seoul)/page.tsx`)이 첫 방문자에게 히어로 역할을 겸하지만 같은 제품 토큰을 쓴다. 별도의 마케팅 기하를 만들지 않는다 — 필요해지면 그때 이 절에 표면 이름과 함께 기록한다.

## 3. Typography Rules

### Font Family
- **표준 UI 패밀리**: `Pretendard Variable`. `app/globals.css`에서 CDN으로 로드하고 `--font-sans`로 전 화면에 적용한다.
- **Fallback**: `Pretendard`, `-apple-system`, `BlinkMacSystemFont`, `system-ui`, `sans-serif`.
- **Monospace**: 표준 monospace 토큰 없음. 숫자 정렬은 별도 폰트가 아니라 `tabular-nums`로 처리한다(34개 파일에서 사용 중).

### Current type hierarchy

| Role | Size | Weight | 유틸 | 용도 |
|---|---:|---:|---|---|
| H1 | 30px (모바일) / 36px (sm+) | 600 | `text-3xl sm:text-4xl` | 홈 인사말. 이 크기를 쓰는 곳은 홈뿐이다 |
| **Data XL** | **28px** | **700** | `text-data-xl` | **결론이 되는 수** — 현재가·핵심 지표. `tabular-nums`를 함께 붙인다 |
| H2 | 20px | 700 | `text-xl` | 페이지 제목 |
| **Data L** | **20px** | **600** | `text-data-l` | 등락률·보조 수치. `tabular-nums`를 함께 붙인다 |
| H3 | 16px | 600 | `text-base` | 섹션·카드 제목 |
| Body | 14px | 400 | `text-sm` | 지배적 본문 크기 |
| Body Small | 12px | 400 | `text-xs` | 보조 설명·캡션 — **가장 작은 단계다** |

본문 기본이 16px이 아니라 14px이다. 정보 밀도가 높은 대시보드 화면이 다수여서 생긴 차이이며, 홈처럼 읽기 중심인 화면에서는 16px를 쓴다.

**12px 아래를 만들지 않는다.** `text-[10px]`·`text-[11px]`은 스케일 밖이다 — 41개 파일에 퍼져 있는 것은
정리 대상이지 선례가 아니다. 캡션이 작아야 할 것 같으면 크기를 줄이지 말고 `text-foreground-muted`로 **무게를 낮춘다.**

**데이터 화면에는 Data 단계를 반드시 쓴다.** 결론이 되는 수를 본문(14px)과 같은 크기로 두면 화면이 평평해진다 —
"결론 먼저"라고 적어 두고 전부 11px로 그리면 결론이 없는 것과 같다.

## 4. Component Stylings

### Button

크기별로 **높이·radius·폰트가 함께** 바뀐다. 셋 중 하나만 바꾸지 않는다.

| Size | Height | Radius | Font | 용도 |
|---|---:|---:|---|---|
| sm | 32px | 8px (`rounded-lg`) | 13px / 500 | 인라인·칩·테이블 액션 |
| md | 40px | 12px (`rounded-xl`) | 14px / 500 | 기본 폼·대화상자 |
| lg | 48px | 12px (`rounded-xl`) | 15px / 600 | 섹션 주요 액션 |
| xl | 56px | 16px (`rounded-2xl`) | 17px / 600 | 화면 단위 주요 액션(주문·가입) |

- Variants: `default`(채운 primary) · `weak`(`#F0EDE6` / `#991B1B`) · `outline` · `ghost` · `destructive`
- States: loading, disabled, pressed, keyboard focus
- **로딩 중 너비를 유지한다.** 라벨이 "청산"에서 "청산 중…"으로 바뀌며 버튼이 들썩이지 않게 한다
- Pressed는 `scale(0.98)`로 표현한다 — local extension(§15 참조)
- `rounded-full`은 아이콘 버튼·아바타·칩·뱃지·세그먼트 토글에 쓴다. **액션 버튼에는 쓰지 않는다**(§5)

> local deviation: 레퍼런스의 large는 14px radius지만 Tailwind 스케일에 14px가 없어 12px를 쓴다. 값을 억지로 만들지 않고 인접 단계를 택했다.

### Text Field
- 높이·radius는 Button의 sm/md 단계를 따른다
- States: focus, error, disabled, read-only
- Focus는 브랜드 톤 링으로 표시한다. 라벨과 오류 문구를 함께 둔다

### Badge
- 상태·등급 표시용이며 **액션이 아니다**. 클릭 가능해 보이게 만들지 않는다
- Radius 6px(`rounded-md`) 또는 `rounded-full`

### Agreement
- 회원가입 약관 동의. checked / unchecked / disabled와 "전체 동의" 계층을 가진다
- 필수·선택을 라벨에 명시하고, 약관 본문 링크는 별도 탭으로 연다

### Marketing Primary
해당 없음 — §2 "Marketing-web roles" 참조.

### Marketing Dark
해당 없음 — §2 "Marketing-web roles" 참조.

## 5. Layout Principles

### Spacing System
- 사용 스케일: 4px, 8px, 12px, 16px, 24px, 32px
- 이 여섯 단계 밖의 값을 새로 만들지 않는다

### Grid & Container
- 워크스페이스는 3패널(자료 340px / 스테이지 / 채팅 360px)이 xl 기준이고, lg에서 2단, 그 아래에서는 탭 전환으로 접힌다
- 콘텐츠 페이지의 최대 폭은 `max-w-6xl`
- **대시보드 화면은 예외다.** 여러 열을 동시에 세우는 화면(`/game`)은 `max-w-[1720px]`까지 연다 —
  1152px에서는 [목록 \| 상세 \| 주문] 3열이 서지 않는다. 읽기 중심 페이지에는 적용하지 않는다
- 모바일 폭은 **375px을 하한으로 잡는다**

### Border Radius Scale

radius는 **요소의 위계**로 정해진다. 크기로 정하지 않는다.

| 대상 | radius |
|---|---|
| 액션 버튼 | 8px / 12px / 16px — §4 크기 표를 따른다 |
| 카드·패널·모달 | 12px 또는 16px |
| **홈 입력창** | **24px**(`rounded-3xl`) — 아래 단독 항목 참조 |
| 칩·뱃지·세그먼트 토글 | `full`(9999px) |
| 아이콘 버튼·아바타 | `full`(9999px) |

**홈 입력창만 24px다**(`components/seoul/ChatInput.tsx`). 홈에는 이 요소 하나뿐이고 제품의 관문이라
카드와 같은 기하로 두면 "여러 카드 중 하나"로 보인다. 레퍼런스(Gemini·Grok)도 이 자리를 가장 둥글게 만든다.
**다른 화면의 입력에는 쓰지 않는다** — 그쪽은 여전히 Button의 sm/md 단계를 따른다.

> 이 상자는 하나여야 한다. shadcn `Textarea`는 자체 `border`와 focus ring을 갖고 있어 그대로 쓰면
> 둥근 form 안에 각진 상자가 하나 더 생긴다. 안쪽은 `border-0 rounded-none focus-visible:ring-0`으로
> 무력화하고 focus 표시는 바깥 form이 `focus-within`으로 한 번만 낸다.

칩과 뱃지에 알약을 쓰는 이유는 관례라서가 아니라, 위계가 낮은 요소를 버튼 스케일과 **섞이지 않게** 하기 위해서다. 알약은 "이건 주요 액션이 아니다"를 형태로 말한다. 반대로 액션 버튼이 알약이면 그 구분이 사라진다.

- Tailwind 기본 스케일을 그대로 쓴다. `--radius-*`를 재정의하지 않는다 — 재정의하면 유틸 이름과 실제 값이 어긋나고, 이 문서를 대조하는 훅도 기본 스케일로 판정한다
- 위 표 밖의 단계(`rounded-sm`, `rounded-3xl`)는 UI 요소에 쓰지 않는다
- **반응형 리셋은 예외다.** `lg:rounded-none`처럼 좁은 폭에서 준 radius를 넓은 폭에서 **되돌리는** 것은
  새 단계를 만드는 게 아니다(예: 모바일 바텀시트 `rounded-t-2xl` → 데스크탑 컬럼에서 해제).
  같은 요소가 두 레이아웃을 오갈 때 쓰고, 처음부터 각진 요소에 쓰지 않는다

**예외 — 데이터를 그리는 요소.** 차트 막대·게이지·스파크라인 내부는 이 표를 따르지 않는다.
높이 8px짜리 기여도 막대(`components/stock/SignalBreakdown.tsx`)에 6px radius를 주면 형태가
뭉개져 값을 읽을 수 없다. 여기서 radius는 장식이 아니라 **데이터 표현의 일부**다.

## 6. Depth & Elevation

그림자는 표준 토큰으로 승격하지 않는다. 현재 저장소에서 그림자는 21곳에서만 쓰이며, 대부분의 계층은 색 면(`canvas` 위 `surface`)과 `border`로 구분된다. 이 방식을 유지한다.

그림자가 필요한 경우는 **떠 있는 표면**(모달·팝오버·토스트)뿐이다. 카드나 패널에 그림자를 더해 계층을 만들지 않는다.

**배경 장식은 홈에만 있다**(`.home-glow`, `app/globals.css`). 값이 놓이는 화면(워크스페이스·게임·어드민)에는
깔지 않는다 — 숫자 위에 색면이 깔리면 읽기가 방해된다. 다른 화면에 분위기를 더하고 싶으면 그라데이션이 아니라 여백을 쓴다.

구성은 두 겹이다.
- **빛 두 덩이**: 브랜드 톤 5%·3%를 서로 다른 자리에 겹친다. 한 덩이를 크게 깔면 상단이 통째로 분홍으로 물들어
  크림 배경(`#FDFAF2`)이 사라진다 — 농도보다 **위치를 어긋나게 두는 것**이 핵심이다
- **도트 격자**(24px, foreground 7%): 빈 면에 결을 준다. 그라데이션만으로는 "비어 있음"이 "미완성"으로 읽힌다.
  화면 끝까지 깔면 지저분하므로 중앙에서 바깥으로 사라지는 마스크를 씌운다

> 마스크의 `#000`은 색이 아니라 알파다("여기는 보이게"). 팔레트 규칙과 무관하며 색 감사에서 제외한다.

**홈 입력창의 그림자는 §6의 예외다.** 이 화면의 유일한 조작 대상이라 면에서 떠 있어야 하고,
"카드에 그림자를 더해 계층을 만들지 않는다"가 막으려던 것(카드 여러 장의 그림자 경쟁)이 여기서는 일어나지 않는다.

## 7. Do's and Don'ts

### Do
- 버튼 크기를 바꿀 때 높이·radius·폰트를 함께 바꾼다.
- 로딩·비활성·눌림·키보드 포커스 상태를 유지한다.
- 뱃지는 상태 정보로만 쓴다.
- 새 화면을 만들 때 §4의 크기 표에서 고른다.
- 모바일 폭 375px에서 먼저 확인한다.

### Don't
- 새 radius·높이·간격 값을 만들지 않는다. 표에 있는 것에서 고른다.
- 액션 버튼에 `rounded-full`을 쓰지 않는다. 칩·뱃지·세그먼트 토글은 예외다(§5).
- 카드·패널에 그림자를 더해 계층을 만들지 않는다.
- 크림 배경(`#FDFAF2`)을 흰색으로 바꾸지 않는다. 그 반대도 마찬가지다.
- 검증되지 않은 모션 곡선을 표준인 것처럼 쓰지 않는다 — local extension으로 표기한다.

## 8. Responsive Behavior

- 하한은 375px(iPhone SE)이다. 320px은 지원 범위 밖으로 둔다
- 워크스페이스 3패널은 lg(1024px) 미만에서 탭으로 접힌다. 패널은 한 번만 마운트하고 표시만 전환한다 — 지도·차트 인스턴스가 두 번 생기지 않게 하기 위한 의도된 구조다
- 상단 내비는 sm(640px) 미만에서 아이콘 3개 + 햄버거로 접힌다
- 어드민은 lg 미만에서 사이드바가 하단 탭바로 바뀌며 `env(safe-area-inset-bottom)`을 적용한다

## 9. Agent Prompt Guide

- "primary xl 버튼을 만들어줘 — `#991B1B` 배경, 흰 텍스트, 56px 높이, 16px radius, 17px/600, loading·disabled·pressed·focus 포함."
- "weak 보조 버튼 — `#F0EDE6` 배경, `#991B1B` 텍스트, 40px 높이, 12px radius."
- "새 입력 필드는 Button의 md 단계 기하를 따르고 focus 링은 브랜드 톤으로."
- "여기 없는 컴포넌트를 만들면 확장(extension)이라고 표시하고, 검증된 것처럼 쓰지 않는다."

## 10. Voice & Tone

전문성을 과시하지 않고 판단에 필요한 것만 건네는 안내자로 말한다. 문장은 짧고 직접적이되, 짧게 쓰는 것 자체가 목적은 아니다. 사용자가 값의 의미를 이해하고, 다음에 무엇을 할지 알고, 막혔을 때 빠져나올 수 있어야 한다.

숫자를 다루는 화면에서는 무엇을 근거로 한 값인지와 기준 시점을 함께 말한다. 상권·주식은 결과가 사용자의 돈에 연결되므로 **단정과 지시를 피한다** — "오를 것이다"가 아니라 무엇이 관측되었는지를 말한다. 모호한 위로, 설명 없는 약어, 기관 화법을 쓰지 않는다.

## 11. Brand Narrative

<!-- omd:limitation Reference §11 requires project-specific facts. Replace before shipping; do not fabricate. -->

[FILL IN: 이 서비스가 무엇을 바꾸려 하는지, 그 판단이 어디서 나왔는지 — 창립 시점과 핵심 thesis 한 문장]

## 12. Principles

<!-- omd:limitation Reference §12 requires project-specific facts. Replace before shipping; do not fabricate. -->

[FILL IN: 이 프로젝트가 실제로 지켜온 설계 원칙 3-5개. 일반적인 디자인 격언이 아니라 이 저장소에서 반복해 내린 결정을 적는다]

## 13. Personas

<!-- omd:limitation Reference §13 requires project-specific facts. Replace before shipping; do not fabricate. -->

[FILL IN: 실제 사용 맥락 2-4개. 가상의 인구통계가 아니라 이 화면들 앞에 앉은 사람이 무엇을 하려는지]

## 14. States

| Component | State contract |
|---|---|
| Button | fill/weak, semantic color, loading(너비 유지), disabled, pressed, keyboard focus |
| Text Field | focus, error, disabled, read-only |
| Dialog | open/closed, 포커스 트랩, 스크롤 락, Escape |
| Agreement | checked, unchecked, disabled, 전체동의 계층 |
| 데이터 패널 | loading(스켈레톤), empty, error, 부분 데이터 |

데이터 화면은 네 번째 행이 특히 중요하다. 값이 없는 것과 아직 오지 않은 것과 실패한 것을 같은 화면으로 보여주지 않는다.

## 15. Motion & Easing

레퍼런스에는 표준 모션 토큰이 없다. 아래 값은 이 프로젝트의 **local extension**이며, 공식 근거가 아니라 프로젝트 내부 합의다.

- Duration 3단: **150ms**(상태 전환 — hover, pressed) · **200ms**(요소 진입·퇴장) · **280ms**(모달·시트)
- Easing: `cubic-bezier(0.22, 1, 0.36, 1)`
- 리스트 stagger는 항목당 40ms를 넘기지 않는다

모션을 쓰는 자리는 다섯 곳으로 제한한다 — 모달·시트 진입, 리스트 stagger, 숫자 변화, 홈 첫 진입, **지수 티커 바**. 채팅 스트리밍처럼 이미 빠르게 갱신되는 곳에는 얹지 않는다(오히려 느려 보인다).

**티커 바는 duration 3단 밖이다.** 끝없이 도는 배경 흐름이라 "상태 전환·진입·모달"이라는 3단의 축에 놓이지 않는다.
속도는 호출부가 `--duration`으로 주고 기본값은 40s다(`components/ui/marquee.tsx`).

**모션 라이브러리는 여전히 쓰지 않는다.** Magic UI에서 가져온 marquee는 의존성이 0인 순수 CSS다.
`motion`이 필요한 컴포넌트(border-beam · number-ticker · animated-list)는 도입하지 않았다 —
뒤의 둘은 이미 있는 `CountUp`·`animate-fade-in-up`과 하는 일이 같다.

`prefers-reduced-motion: reduce`에서 전부 꺼진다. 이건 선택이 아니다.
