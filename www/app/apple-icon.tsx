import { ImageResponse } from "next/og";

// Safari "Dock에 추가"·iOS 홈 화면 아이콘 — SVG 파비콘(icon.svg)을 쓰지 않고 PNG를 찾는다.
// icon.svg와 같은 적색 핀. 모서리는 OS가 깎으므로 배경은 꽉 채운다.
export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#a51c1c",
        }}
      >
        <svg width="140" height="140" viewBox="0 0 64 64">
          <path d="M32 54c-1.6 0-14-13.2-14-24a14 14 0 0 1 28 0c0 10.8-12.4 24-14 24Z" fill="#fff" />
          <circle cx="32" cy="30" r="5.5" fill="#a51c1c" />
        </svg>
      </div>
    ),
    size,
  );
}
