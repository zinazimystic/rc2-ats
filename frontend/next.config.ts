import type { NextConfig } from "next";

// The browser only ever talks to this Next.js origin; /api/* is proxied to FastAPI.
// => same-origin httpOnly cookie auth, no CORS, no token in JS.
const backend = process.env.BACKEND_URL ?? process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  experimental: {
    proxyTimeout: 180000, // question generation can take ~60 s
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
