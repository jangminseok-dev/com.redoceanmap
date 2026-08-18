// 3D 브랜드 오브젝트 — 홈 전용(핸드오프 §6 절제형 3D · 구현 등급 A: CSS transform만, 의존성 0).
// 상권 지형을 추상화한 blob 레이어 4장이 천천히 돌고, 브랜드 핀이 그 위에 떠 있다.
// 데이터가 놓이는 화면에는 두지 않는다 — 값 읽기를 방해하는 3D는 금지(§6).
// prefers-reduced-motion에서는 globals.css 전역 규칙이 회전·펄스를 멈춘다(정적 프레임 유지).
export default function BrandObject() {
  return (
    <div className="brand-object" aria-hidden>
      <div className="brand-object-stage">
        <span className="brand-layer brand-layer-1" />
        <span className="brand-layer brand-layer-2" />
        <span className="brand-layer brand-layer-3" />
        <span className="brand-layer brand-layer-4" />
      </div>
      <span className="brand-object-pin">
        <svg width="26" height="33" viewBox="0 0 16 20" fill="none">
          <path
            d="M8 0C3.6 0 0 3.6 0 8c0 6 8 12 8 12s8-6 8-12c0-4.4-3.6-8-8-8z"
            fill="var(--brand)"
          />
          <circle cx="8" cy="8" r="2.5" fill="var(--background)" />
        </svg>
      </span>
      <span className="brand-object-floor" />
    </div>
  );
}
