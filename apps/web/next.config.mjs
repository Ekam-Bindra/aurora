/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Allows importing the shared @aurora/config preset from the monorepo.
  transpilePackages: ["@aurora/config"],
};

export default nextConfig;
