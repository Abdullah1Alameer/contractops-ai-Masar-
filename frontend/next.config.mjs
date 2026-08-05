/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    optimizePackageImports: ["lucide-react"],
  },
};

// Bundle analysis: ANALYZE=1 npm run build (requires @next/bundle-analyzer optional install).
// Next.js --profile can be used for server/client compile profiling during build.

export default nextConfig;
