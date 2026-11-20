import { networkInterfaces } from "node:os";

import type { NextConfig } from "next";

// The browser only ever talks to the Next server; it forwards API and clip-file requests to the
// local FastAPI backend. One port to open, no CORS, and the API itself stays bound to localhost,
// so a phone on the same Wi-Fi (or a Tailscale device) can use the app with the same data.
const API = process.env.PEAKCUT_API ?? "http://127.0.0.1:8000";

// Let other devices on this machine's networks load dev-mode assets (Next blocks unknown origins).
const lanHosts = Object.values(networkInterfaces())
  .flat()
  .filter((n) => n && n.family === "IPv4" && !n.internal)
  .map((n) => n!.address);

const nextConfig: NextConfig = {
  allowedDevOrigins: [...lanHosts, "*.ts.net"],
  experimental: {
    proxyTimeout: 300_000, // AI caption rewrites for a whole job can take a while
  },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API}/api/:path*` },
      { source: "/files/:path*", destination: `${API}/files/:path*` },
      { source: "/health", destination: `${API}/health` },
    ];
  },
};

export default nextConfig;
