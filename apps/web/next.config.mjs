/** @type {import('next').NextConfig} */
const API_DEV_TARGET = process.env.AURORA_API_DEV_URL ?? "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
  // Allows importing the shared @aurora/config preset from the monorepo.
  transpilePackages: ["@aurora/config"],
  async rewrites() {
    // Lets the browser call same-origin `/api/v1/*` during `pnpm dev`.
    return [
      {
        source: "/api/v1/:path*",
        destination: `${API_DEV_TARGET}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
