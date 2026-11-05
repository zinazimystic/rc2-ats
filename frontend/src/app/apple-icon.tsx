import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", background: "#4f46e5" }}>
        <svg width="120" height="120" viewBox="0 0 32 32" fill="none">
          <g stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <path d="M11 8.5v15" />
            <path d="M11 8.5h5.2a4.3 4.3 0 0 1 0 8.6H11" />
            <path d="M16 17.2l4.2 4.6" />
          </g>
          <circle cx="23" cy="23.6" r="2.7" fill="#fff" />
        </svg>
      </div>
    ),
    size,
  );
}
