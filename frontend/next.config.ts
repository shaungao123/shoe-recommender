import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // A stray lockfile in the user home dir otherwise makes Next mis-infer the workspace root.
  turbopack: { root: __dirname },
  output: "standalone",
};

export default nextConfig;
