type Props = {
  size?: number;
  /** 큰 아바타에만 링·글로우를 두른다 — 말풍선 옆 작은 아바타는 얼굴만. */
  ring?: boolean;
  /** 응답 생성 중 — 눈이 깜빡인다. */
  thinking?: boolean;
};

// ROM 마스코트. 3D 렌더 에셋 없이 벡터로만 그린다(빌드 산출물에 이미지 파일이 늘지 않는다).
export default function RobotAvatar({ size = 40, ring = false, thinking = false }: Props) {
  const id = ring ? "rom-hero" : "rom-mini";
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 120"
      role="img"
      aria-label="ROM 챗봇"
      className="shrink-0"
    >
      <defs>
        {/* 링·글로우는 브랜드 레드 톤 — 크림 배경(#FDFAF2) 위에서 파랑 계열은 겉돈다 */}
        <linearGradient id={`${id}-ring`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#991B1B" />
          <stop offset="100%" stopColor="#D97757" />
        </linearGradient>
        <linearGradient id={`${id}-shell`} x1="0.3" y1="0" x2="0.7" y2="1">
          <stop offset="0%" stopColor="#FFFFFF" />
          <stop offset="55%" stopColor="#E8EAEF" />
          <stop offset="100%" stopColor="#B8BDC9" />
        </linearGradient>
        <radialGradient id={`${id}-glow`} cx="0.5" cy="0.5" r="0.5">
          <stop offset="0%" stopColor="#991B1B" stopOpacity="0.14" />
          <stop offset="100%" stopColor="#991B1B" stopOpacity="0" />
        </radialGradient>
      </defs>

      {ring && (
        <>
          <circle cx="60" cy="60" r="56" fill={`url(#${id}-glow)`} />
          <circle
            cx="60"
            cy="60"
            r="52"
            fill="none"
            stroke={`url(#${id}-ring)`}
            strokeWidth="2.5"
          />
        </>
      )}

      {/* 귀 */}
      <rect x="17" y="52" width="10" height="20" rx="5" fill="#8F97A8" />
      <rect x="93" y="52" width="10" height="20" rx="5" fill="#8F97A8" />

      {/* 머리 */}
      <rect x="24" y="30" width="72" height="62" rx="26" fill={`url(#${id}-shell)`} />

      {/* 바이저 */}
      <rect x="34" y="42" width="52" height="38" rx="17" fill="#0A1020" />

      {/* 눈 */}
      <g fill="#38BDF8">
        <circle cx="49" cy="59" r="5.5">
          {thinking && (
            <animate
              attributeName="r"
              values="5.5;1.4;5.5"
              dur="1.8s"
              repeatCount="indefinite"
            />
          )}
        </circle>
        <circle cx="71" cy="59" r="5.5">
          {thinking && (
            <animate
              attributeName="r"
              values="5.5;1.4;5.5"
              dur="1.8s"
              begin="0.12s"
              repeatCount="indefinite"
            />
          )}
        </circle>
      </g>

      {/* 입 */}
      <path
        d="M52 70 Q60 76 68 70"
        fill="none"
        stroke="#38BDF8"
        strokeWidth="2.5"
        strokeLinecap="round"
      />

      {/* 어깨 — 큰 아바타에서만 보인다(작은 크기에선 뭉개진다) */}
      {ring && (
        <path
          d="M38 96 Q60 88 82 96 L82 106 Q60 100 38 106 Z"
          fill="#9AA2B2"
        />
      )}
    </svg>
  );
}
