---
paths:
  - "**/*.ts"
  - "**/*.tsx"
---

## TypeScript 규칙

`www/`(Next.js 16 · React 19 · TS 5)의 실제 코드에서 뽑은 규칙이다.
새 코드는 아래 패턴을 **그대로** 따른다. 기존 코드를 고칠 때는 주변 스타일을 우선한다(Surgical Changes).

### 기본 원칙

- **strict mode 필수** — `www/tsconfig.json`의 `strict: true`를 끄거나 개별 `strict*` 옵션을 완화하지 않는다.
- **`any` 타입 사용 금지** — 예외는 아래 "외부 SDK 경계" 한 곳뿐이다. 값의 모양을 모를 때는 `unknown`을 쓴다.
- **인터페이스보다 타입 별칭 선호** — `type X = { ... }`. `interface`는 `declare global` 확장에만 쓴다
  (전 코드베이스에서 `components/seoul/MapView.tsx:6`의 `Window` 하나뿐).
- `enum`을 쓰지 않는다. 대신 문자열 리터럴 유니언(`"UP" | "DOWN" | "NEUTRAL"`)을 쓴다.
- 임포트는 `@/` 경로 별칭을 쓰고, 타입만 가져올 때는 `import type`으로 분리한다.

```ts
import type { SignalContribution, StockAnalyzeResult } from "@/lib/types";
import { formatPrice } from "@/lib/currency";
```

### 백엔드 계약 타입은 `lib/types.ts` 한 곳에

- 백엔드 응답 타입은 `lib/types.ts`에 모으고, 엔드포인트별 주석 헤더로 구획한다
  (`// ── GET /stock/{symbol}/forecast ──`). 어드민 전용은 `lib/adminApi.ts` 상단에 둔다.
- **필드명은 백엔드 응답을 그대로 쓴다.** BFF(`app/api/*`)를 거쳐 camelCase로 오면 camelCase,
  FastAPI를 직접 호출해 snake_case로 오면 snake_case를 유지하고 주석으로 명시한다.
  임의로 변환하지 않는다 — 변환 계층이 곧 버그 지점이다.

```ts
// ── POST /stock/analyze (직접 호출 — snake_case DTO) ──
export type StockAnalyzeResult = {
  sentiment_label: string;
  atr_pct: number;
  // 신규 필드 — 구버전 응답 호환을 위해 옵셔널
  score?: number;
  neutral_reason?: "atr_veto" | "volume_confirm" | null;
};
```

- **`| null`과 `?`를 구분한다.** 백엔드가 값을 항상 보내지만 비어 있을 수 있으면 `T | null`,
  구버전 응답에 필드 자체가 없을 수 있으면 `?`. 둘 다면 `field?: T | null`.
- 파생 타입은 새로 선언하지 않고 인덱스 접근·`NonNullable`로 좁힌다.

```ts
latest: AreaStatsDetail["latest"];
spending: NonNullable<AreaDetail["spending"]>;
signal?: SignalContribution["key"];
```

### fetch 래퍼는 제네릭 하나로

조회 함수는 개별 타입 단정(`as T`) 없이 제네릭 래퍼의 반환 타입으로만 계약을 표현한다.
에러는 `ApiError`(status 보유)로 통일한다.

```ts
async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`/api/backend${path}`);
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new ApiError(res.status, detail?.detail ?? "요청에 실패했습니다.");
  }
  return res.json();
}

export const fetchStockQuote = (symbol: string): Promise<StockQuote> =>
  getJson(`/stock/${encodeURIComponent(symbol)}/quote`);
```

- 브라우저 fetch는 반드시 `/api/backend` rewrite를 경유한다(절대 URL 금지).
- 요청 본문이 임의 객체면 파라미터 타입은 `unknown`으로 받는다: `postWithAuth(url: string, body: unknown)`.
- 쿼리스트링은 문자열 연결 대신 `URLSearchParams`를 쓰고, 경로 삽입 값은 `encodeURIComponent`로 감싼다.

### 컴포넌트 props

- props 3개 이하 & 재사용 없음 → **인라인 객체 타입**.
- props 4개 이상이거나 다른 파일에서 참조 → `type Props`(파일 내 단독 컴포넌트) 또는
  `type <Name>Props`(같은 파일에 컴포넌트 여러 개).
- props 타입은 컴포넌트가 export되어도 기본적으로 export하지 않는다. 다른 곳에서 쓰는 형태만 export한다
  (예: `export type MapPin`).

```tsx
export default function Disclaimer({ className = "" }: { className?: string }) {}

type CandleChartProps = {
  symbol: string;
  timeframe: "1d" | "5m";
  onSelect: (id: string) => void;
};
```

- children은 `React.ReactNode`, 이벤트는 `React.FormEvent<HTMLFormElement>` /
  `React.ChangeEvent<HTMLInputElement>` / `React.DragEvent`로 명시한다. `React.FC`는 쓰지 않는다.
- 폼 상태는 [[www/_docs/REACT_RULES|REACT_RULES]]가 우선한다(FormData 패턴 → 타입은 위 `FormEvent` 그대로).

### 라벨·스타일 맵은 `Record`로

문자열 → 표시값 매핑은 `if/switch` 대신 상수 `Record`로 둔다. 키가 유니언이면 유니언을 키 타입으로 써서
값 누락을 컴파일 에러로 잡는다.

```ts
type Tone = "up" | "down" | "flat";
const TONE_TEXT: Record<Tone, string> = { up: "...", down: "...", flat: "..." };

const UNIT: Record<ScoreComponent["key"], string> = { ... };
```

백엔드가 문자열을 자유롭게 보내는 축(등급·업종 등)은 `Record<string, T>`로 두고
**반드시 폴백을 붙인다**: `(FRESHNESS[d.freshness] ?? FRESHNESS.unknown).label`.

### `as const`

리터럴 배열을 map으로 돌릴 때, 그리고 차트 옵션 객체에 `as const`를 붙여 리터럴 타입을 보존한다.
`satisfies`는 현재 코드베이스에서 쓰지 않는다.

```tsx
{(["1d", "5m"] as const).map((tf) => ...)}
{([4, 8, 20] as const).map((q) => ...)}
```

### zustand 스토어

- 상태 타입은 `type <Name>State`로 파일 내부에 두고 **export하지 않는다**. 재사용되는 도메인 타입
  (`Message`, `User`, `ChatEngine`)만 export한다.
- 액션 시그니처를 상태 타입에 함께 선언하고, `create<State>((set, get) => ...)`로 제네릭을 명시한다.
  구현부 파라미터에는 타입을 다시 적지 않는다(추론에 맡긴다).
- 미들웨어를 쓸 때만 커링 형태: `create<DensityState>()(persist(...))`.

```ts
type UIState = {
  user: User | null;
  openAuth: (mode: AuthMode) => void;
};

export const useUIStore = create<UIState>((set) => ({
  user: null,
  openAuth: (mode) => set({ authOpen: true, authMode: mode }),
}));
```

### 매직값은 이름 있는 상수로

임계값·기본값을 식 안에 직접 쓰지 않고 파일 상단 `const`(SCREAMING_SNAKE)로 올린다.
백엔드와 공유하는 값이면 어느 모듈과 맞춘 값인지 주석에 남긴다.

```ts
// 백엔드 stock_narrator.py와 같은 임계값 — 화면 라벨과 해설 문장이 어긋나지 않게 맞춘다
const RSI_OVERSOLD = 30;
const EDGE_MIN_PP = 3;
```

### 외부 SDK 경계 — `any`가 허용되는 유일한 곳

타입 정의가 없는 스크립트 로드형 SDK(카카오맵)에 한해 `declare global` + `any`를 쓴다.
이 경계는 `components/seoul/MapView.tsx`에 격리하고, 밖으로 나가는 값은 자체 타입으로 좁혀 내보낸다
(`export type MapPin = { id: string; lat: number; lng: number }`).
**새로운 `any`를 다른 파일에 도입하지 않는다.**

### 검증

타입 변경을 포함한 작업은 아래로 검증하고, 결과를 한 줄로 보고한다.

```bash
cd www && npx tsc --noEmit
```

`.next/types`에 구 경로 캐시가 남아 오탐하면 `rm -rf .next/types` 후 재실행한다.
