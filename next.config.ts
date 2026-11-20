import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // The dev badge sits over the mobile bottom bar; hide it.
  devIndicators: false,
};

export default nextConfig;
