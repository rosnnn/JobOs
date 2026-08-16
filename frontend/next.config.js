/** @type {import('next').NextConfig} */
const isDev = process.env.NODE_ENV !== "production";
const backend = process.env.BACKEND_URL || (isDev ? "http://127.0.0.1:8000" : "http://api:8000");

const nextConfig = {
  reactStrictMode: true,
  distDir: isDev ? ".next-dev" : ".next",
  webpack: (config, { dev }) => {
    if (dev) {
      // Avoid intermittent Windows filesystem cache corruption in .next during HMR.
      config.cache = false;
    }
    return config;
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backend}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
